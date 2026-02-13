# City Breathing

Animated heatmap of ~1.8M NYC Citi Bike trips from January 2026, showing the city "breathing" through a 24-hour cycle.

Sparse nighttime to packed daytime to sparse nighttime, looping seamlessly.

## Preview

**Peak hour (5:00 PM)** - ~4,865 avg rides/hr

![Peak](output/city_breathing_peak.png)

**Night (3:00 AM)** - ~195 avg rides/hr

![Night](output/city_breathing_night.png)

## How it works

1. Downloads ~1.8M Citi Bike trip records (January 2026) from S3
2. Groups trips by hour and renders each as a datashader heatmap
3. Applies multi-layer neon glow on a dark satellite basemap
4. Interpolates 120 frames across 24 hours for smooth animation
5. Outputs a 10-second looping MP4 + GIF

## Stack

- **pandas** - data loading
- **datashader** - fast point aggregation for millions of trips
- **Pillow** - image compositing, neon glow, text overlays
- **contextily** - satellite basemap tiles (Esri)
- **imageio** - MP4 and GIF encoding

## Run it

```bash
pip install -r requirements.txt
python city_breathing.py
```

Data is auto-downloaded on first run. Output goes to `output/`.

## Output

| File | Description |
|------|-------------|
| `city_breathing.mp4` | 10-second looping animation (~1 MB) |
| `city_breathing.gif` | Same animation as GIF (~62 MB) |
| `city_breathing_peak.png` | Peak hour thumbnail |
| `city_breathing_night.png` | Night thumbnail |
