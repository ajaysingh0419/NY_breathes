"""
City Breathing — NYC Citi Bike Animated Heatmap
Turns ~1.8M NYC Citi Bike trips from January 2026 into an animated neon
heatmap showing the city "breathing" through a 24-hour cycle.

Sparse nighttime (magenta glow on dark satellite map) -> packed daytime
(bright pink/white-hot) -> sparse nighttime, looping seamlessly.

Output: output/city_breathing.mp4 and output/city_breathing.gif
"""

import os
import zipfile
import urllib.request
import pandas as pd
import datashader as ds
import datashader.transfer_functions as tf
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
Image.MAX_IMAGE_PIXELS = None
import geopandas as gpd
from shapely.geometry import box
import contextily as cx
import imageio.v3 as iio

# --- Paths ---
DATA_DIR = "data"
OUTPUT_DIR = "output"
BOROUGH_FILE = os.path.join(DATA_DIR, "nyc_boroughs.geojson")
CSV_PATH = os.path.join(DATA_DIR, "citibike_202601.csv")

# --- NYC bounding box ---
XMIN, XMAX = -74.06, -73.87
YMIN, YMAX = 40.63, 40.84

# --- Output dimensions ---
MAP_HEIGHT = 800
BAR_AREA = 100
WIDTH = 800
HEIGHT = MAP_HEIGHT + BAR_AREA
SUPERSAMPLE = 1
RENDER_W = WIDTH * SUPERSAMPLE
RENDER_H = MAP_HEIGHT * SUPERSAMPLE

# --- Animation ---
INTERP_FRAMES = 5  # 24 hours x 5 = 120 total frames
FPS = 12           # 120 / 12 = 10-second loop

# --- Color ramp: deep magenta -> hot pink -> white-hot ---
CMAP = [
    "#35002A", "#4D0040", "#6B005A", "#8C0070", "#B00088",
    "#D020A0", "#E845B0", "#F060C0", "#F580D0", "#FF99DD",
    "#FFC0E8", "#FFDDF4", "#FFF0FB",
]

HOUR_LABELS = [
    "12:00 AM", "1:00 AM", "2:00 AM", "3:00 AM", "4:00 AM", "5:00 AM",
    "6:00 AM", "7:00 AM", "8:00 AM", "9:00 AM", "10:00 AM", "11:00 AM",
    "12:00 PM", "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM", "5:00 PM",
    "6:00 PM", "7:00 PM", "8:00 PM", "9:00 PM", "10:00 PM", "11:00 PM",
]


# --- Data download ---

def download_data():
    """Download January 2026 Citi Bike data from S3. Returns path to CSV."""
    if os.path.exists(CSV_PATH):
        return CSV_PATH

    url = "https://s3.amazonaws.com/tripdata/202601-citibike-tripdata.zip"
    zip_path = os.path.join(DATA_DIR, "citibike_202601.zip")
    print("Downloading January 2026 Citi Bike data...")
    os.makedirs(DATA_DIR, exist_ok=True)
    urllib.request.urlretrieve(url, zip_path)

    with zipfile.ZipFile(zip_path, "r") as zf:
        csv_names = sorted(n for n in zf.namelist() if n.endswith(".csv"))
        if len(csv_names) == 1:
            with zf.open(csv_names[0]) as src, open(CSV_PATH, "wb") as dst:
                dst.write(src.read())
        else:
            print(f"  Found {len(csv_names)} CSV files, concatenating...")
            with open(CSV_PATH, "wb") as dst:
                for i, name in enumerate(csv_names):
                    with zf.open(name) as src:
                        if i == 0:
                            dst.write(src.read())
                        else:
                            first_line = True
                            for line in src:
                                if first_line:
                                    first_line = False
                                    continue
                                dst.write(line)
    os.remove(zip_path)
    return CSV_PATH


def download_boroughs():
    """Download NYC borough boundary GeoJSON."""
    url = (
        "https://raw.githubusercontent.com/codeforgermany/"
        "click_that_hood/main/public/data/new-york-city-boroughs.geojson"
    )
    print("Downloading NYC borough boundaries...")
    os.makedirs(DATA_DIR, exist_ok=True)
    urllib.request.urlretrieve(url, BOROUGH_FILE)


def load_data():
    """Load January 2026 Citi Bike data. Returns (df, total_trips, num_days)."""
    print("Loading January 2026 Citi Bike data...")
    csv_path = download_data()
    df = pd.read_csv(
        csv_path,
        usecols=["started_at", "start_lat", "start_lng"],
        parse_dates=["started_at"],
    )
    df = df.dropna()
    df = df.rename(columns={"start_lng": "lon", "start_lat": "lat"})
    df = df[
        (df["lon"] > XMIN) & (df["lon"] < XMAX)
        & (df["lat"] > YMIN) & (df["lat"] < YMAX)
    ]
    df["hour"] = df["started_at"].dt.hour
    num_days = df["started_at"].dt.date.nunique()
    total = len(df)
    print(f"  {total:,} trips across {num_days} days")
    for h in range(24):
        count = len(df[df["hour"] == h])
        print(f"    {HOUR_LABELS[h]:>8s}: {count:>8,} total, {count // num_days:>6,} avg/day")
    return df, total, num_days


# --- Basemap ---

def lonlat_to_pixel(lon, lat, w=WIDTH, h=MAP_HEIGHT):
    """Convert longitude/latitude to pixel coordinates on the map."""
    px = (lon - XMIN) / (XMAX - XMIN) * w
    py = (1 - (lat - YMIN) / (YMAX - YMIN)) * h
    return px, py


def _fetch_tiles(source, zoom, label):
    """Fetch map tiles via contextily and return as PIL Image."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    print(f"  Fetching {label} tiles...")
    bbox_gdf = gpd.GeoDataFrame(
        geometry=[box(XMIN, YMIN, XMAX, YMAX)], crs="EPSG:4326"
    )
    bbox_web = bbox_gdf.to_crs(epsg=3857)
    bounds = bbox_web.total_bounds

    fig, ax = plt.subplots(figsize=(WIDTH / 100, MAP_HEIGHT / 100), dpi=100)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(bounds[0], bounds[2])
    ax.set_ylim(bounds[1], bounds[3])
    ax.set_axis_off()
    cx.add_basemap(ax, source=source, zoom=zoom)

    fig.canvas.draw()
    buf = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8)
    w, h = fig.canvas.get_width_height()
    tile_img = Image.frombuffer("RGBA", (w, h), buf.tobytes())
    tile_img = tile_img.convert("RGB").resize((WIDTH, MAP_HEIGHT), Image.LANCZOS)
    plt.close(fig)
    return tile_img


_basemap_cache = {}


def get_basemap():
    """Dark satellite basemap — desaturated, darkened, blue-tinted."""
    if "base" not in _basemap_cache:
        img = _fetch_tiles(cx.providers.Esri.WorldImagery, 14, "satellite basemap")
        arr = np.array(img, dtype=np.float32)
        gray = arr.mean(axis=2, keepdims=True)
        arr = arr * 0.15 + gray * 0.85       # desaturate
        arr = arr * 0.20                       # darken
        arr[:, :, 0] *= 0.7                   # reduce red
        arr[:, :, 1] *= 0.9                   # keep green
        arr[:, :, 2] = np.clip(arr[:, :, 2] * 1.5, 0, 255)  # boost blue
        # Fade bottom to hide tile attribution
        sample = arr[-100:-70, :, :].mean(axis=(0, 1))
        for row in range(70):
            t = row / 70
            arr[-(70 - row), :, :] = sample * (1 - t)
        _basemap_cache["base"] = arr.clip(0, 255).astype(np.uint8)
    return Image.fromarray(_basemap_cache["base"])


# --- Overlays ---

def make_coastline_overlay():
    """Draw faint borough boundary lines."""
    if not os.path.exists(BOROUGH_FILE):
        download_boroughs()

    gdf = gpd.read_file(BOROUGH_FILE)
    gdf = gdf.clip(box(XMIN, YMIN, XMAX, YMAX))

    overlay = Image.new("RGBA", (WIDTH, MAP_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None:
            continue
        polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
        for poly in polys:
            coords = list(poly.exterior.coords)
            pixels = [lonlat_to_pixel(lon, lat) for lon, lat in coords]
            if len(pixels) > 2:
                draw.line(pixels + [pixels[0]], fill=(80, 80, 120, 60), width=2)
            for interior in poly.interiors:
                coords = list(interior.coords)
                pixels = [lonlat_to_pixel(lon, lat) for lon, lat in coords]
                if len(pixels) > 2:
                    draw.line(pixels + [pixels[0]], fill=(80, 80, 120, 35), width=1)
    return overlay


def make_vignette():
    """Radial darkening at the edges for a cinematic look."""
    w, h = WIDTH, MAP_HEIGHT
    Y, X = np.ogrid[:h, :w]
    cx_, cy_ = w / 2, h / 2
    dist = np.sqrt((X - cx_) ** 2 + (Y - cy_) ** 2)
    dist = dist / np.sqrt(cx_ ** 2 + cy_ ** 2)
    alpha = np.clip((dist - 0.50) / 0.50, 0, 1) ** 1.8
    alpha_arr = (alpha * 160).astype(np.uint8)
    vig = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    vig.putalpha(Image.fromarray(alpha_arr))
    return vig


# --- Frame rendering ---

def render_hour(df, hour, cmap):
    """Render one hour's trips as a neon-glowing heatmap layer."""
    subset = df[df["hour"] == hour]
    cvs = ds.Canvas(
        plot_width=RENDER_W, plot_height=RENDER_H,
        x_range=(XMIN, XMAX), y_range=(YMIN, YMAX),
    )
    agg = cvs.points(subset, "lon", "lat")
    img = tf.shade(agg, cmap=cmap, how="log")
    img = tf.spread(img, px=2)
    pil = img.to_pil().convert("RGBA")

    # Multi-layer neon glow
    rgb = pil.convert("RGB")
    alpha_arr = np.array(pil.split()[3], dtype=np.float32)
    result = Image.new("RGBA", pil.size, (0, 0, 0, 0))

    for radius, strength in [(50, 0.5), (20, 0.7), (8, 0.9)]:
        g = rgb.filter(ImageFilter.GaussianBlur(radius))
        a = np.array(Image.fromarray(alpha_arr.astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(radius)), dtype=np.float32)
        layer = g.convert("RGBA")
        layer.putalpha(Image.fromarray(np.clip(a * strength, 0, 255).astype(np.uint8)))
        result = Image.alpha_composite(result, layer)

    result = Image.alpha_composite(result, pil)
    return result.resize((WIDTH, MAP_HEIGHT), Image.LANCZOS), len(subset)


def crossfade(img_a, img_b, t):
    """Linearly blend two images. t=0 gives img_a, t=1 gives img_b."""
    a = np.array(img_a, dtype=np.float32)
    b = np.array(img_b, dtype=np.float32)
    return Image.fromarray((a * (1 - t) + b * t).astype(np.uint8))


# --- Text & UI overlays ---

def get_font(size):
    for name in ["arial.ttf", "ArialMT.ttf", "DejaVuSans.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def add_overlays(img, hour_float, trip_count, total_trips, hourly_counts,
                 coastline, vignette):
    """Compose map overlays + bottom bar chart into a full frame."""
    # Map portion with coastline and vignette
    map_rgba = img.convert("RGBA")
    map_rgba = Image.alpha_composite(map_rgba, coastline)
    map_rgba = Image.alpha_composite(map_rgba, vignette)

    draw_map = ImageDraw.Draw(map_rgba)

    accent = (230, 50, 150, 230)
    title_color = (240, 180, 220, 200)
    sub_color = (200, 120, 160, 140)
    rides_color = (220, 50, 140, 160)
    bar_hi = (230, 50, 150, 200)
    bar_lo = (140, 0, 80, 50)

    # Title
    draw_map.text((30, 22), "NYC CITY BREATHING", fill=title_color, font=get_font(22))
    draw_map.text((32, 48),
                  f"Avg {total_trips:,} Citi Bike rides/day  \u00b7  January 2026",
                  fill=sub_color, font=get_font(13))

    # Current time
    h_idx = int(hour_float) % 24
    h_next = (h_idx + 1) % 24
    frac = hour_float - int(hour_float)
    display_hour = h_next if frac >= 0.5 else h_idx
    draw_map.text((30, 68), HOUR_LABELS[display_hour], fill=accent, font=get_font(56))

    # Trip count
    draw_map.text((34, 132), f"~{trip_count:,} avg rides/hr",
                  fill=rides_color, font=get_font(15))

    # Full frame: map + bar chart area
    bg_color = (8, 10, 16, 255)
    full = Image.new("RGBA", (WIDTH, HEIGHT), bg_color)
    full.paste(map_rgba, (0, 0))
    draw = ImageDraw.Draw(full)

    # Hourly bar chart
    bar_w = 24
    gap = 5
    total_w = 24 * (bar_w + gap) - gap
    x_start = (WIDTH - total_w) // 2
    max_count = max(hourly_counts.values()) if hourly_counts else 1
    max_bar_h = 60
    bar_bottom = HEIGHT - 20

    for h in range(24):
        count = hourly_counts.get(h, 0)
        bar_h = max(2, int((count / max_count) * max_bar_h))
        x = x_start + h * (bar_w + gap)
        y_top = bar_bottom - bar_h
        dist = min(abs(h - hour_float), abs(h - hour_float + 24),
                   abs(h - hour_float - 24))
        color = bar_hi if dist < 0.8 else bar_lo
        draw.rectangle([x, y_top, x + bar_w, bar_bottom], fill=color)

        if h % 6 == 0:
            font_tiny = get_font(9)
            label = f"{h}h"
            tw = draw.textlength(label, font=font_tiny)
            draw.text((x + (bar_w - tw) / 2, bar_bottom + 4), label,
                      fill=(180, 180, 200, 100), font=font_tiny)

    return full.convert("RGB")


# --- Output ---

def save_gif(frames, path):
    print("Saving GIF...")
    quantized = [f.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=1)
                 for f in frames]
    quantized[0].save(
        path, save_all=True, append_images=quantized[1:],
        duration=int(1000 / FPS), loop=0, optimize=True,
    )
    print(f"  GIF: {path} ({os.path.getsize(path) / (1024 * 1024):.1f} MB)")


def save_mp4(frames, path):
    print("Saving MP4...")
    with iio.imopen(path, "w", plugin="pyav") as writer:
        writer.init_video_stream("libx264", fps=FPS)
        for f in frames:
            writer.write_frame(np.array(f))
    print(f"  MP4: {path} ({os.path.getsize(path) / (1024 * 1024):.1f} MB)")


# --- Main pipeline ---

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    df, total_trips, num_days = load_data()

    hourly_totals = df.groupby("hour").size().to_dict()
    hourly_counts = {h: c // num_days for h, c in hourly_totals.items()}
    avg_daily_trips = total_trips // num_days

    print("Building map layers...")
    coastline = make_coastline_overlay()
    vignette = make_vignette()

    # Render 24 key frames (one per hour)
    print("Rendering 24 hourly frames...")
    key_frames = {}
    key_counts = {}
    for h in range(24):
        data_img, count = render_hour(df, h, CMAP)
        basemap = get_basemap()
        comp = Image.alpha_composite(basemap.convert("RGBA"), data_img).convert("RGB")
        key_frames[h] = comp
        key_counts[h] = hourly_counts[h]
        print(f"  {HOUR_LABELS[h]:>8s} — {hourly_counts[h]:>6,} avg/day")

    # Interpolate between key frames for smooth animation
    total_frames = 24 * INTERP_FRAMES
    print(f"Interpolating to {total_frames} frames...")
    all_frames = []
    prev_frame = None

    for i in range(total_frames):
        hour_float = (i / INTERP_FRAMES) % 24
        h_a = int(hour_float) % 24
        h_b = (h_a + 1) % 24
        t = hour_float - int(hour_float)

        blended = crossfade(key_frames[h_a], key_frames[h_b], t)

        if prev_frame is not None:
            blended = crossfade(prev_frame, blended, 0.75)
        prev_frame = blended

        trip_count = int(key_counts[h_a] * (1 - t) + key_counts[h_b] * t)

        final = add_overlays(
            blended, hour_float, trip_count, avg_daily_trips,
            hourly_counts, coastline, vignette,
        )
        all_frames.append(final)

        if (i + 1) % INTERP_FRAMES == 0:
            print(f"  Frame {i + 1}/{total_frames}")

    # Save outputs
    save_gif(all_frames, os.path.join(OUTPUT_DIR, "city_breathing.gif"))
    try:
        save_mp4(all_frames, os.path.join(OUTPUT_DIR, "city_breathing.mp4"))
    except Exception as e:
        print(f"  MP4 failed ({e}), GIF is your output.")

    # Save thumbnails
    peak_hour = max(hourly_counts, key=hourly_counts.get)
    all_frames[peak_hour * INTERP_FRAMES].save(
        os.path.join(OUTPUT_DIR, "city_breathing_peak.png"))
    all_frames[3 * INTERP_FRAMES].save(
        os.path.join(OUTPUT_DIR, "city_breathing_night.png"))

    print(f"\nDone! {total_frames} frames, {total_frames / FPS:.1f}s loop")


if __name__ == "__main__":
    main()
