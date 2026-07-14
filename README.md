
# 🌆 City Breathing
Animated geospatial heatmap of ~1.8M NYC Citi Bike trips (January 2026), visualizing how the city “breathes” over a 24-hour cycle.

From sparse 3 AM streets to peak 5 PM congestion, the animation loops seamlessly to reveal urban mobility patterns at scale.

---

## 🚀 Project Overview

City Breathing transforms raw Citi Bike trip records into a high-performance, time-aware geospatial visualization pipeline.

It processes ~1.8 million trip records, aggregates them by hour, renders datashader heatmaps, and outputs a production-ready looping animation (MP4 + GIF).

This project demonstrates scalable data transformation, spatial analytics, and efficient rendering of large datasets.

---

## 📊 What This Demonstrates

✔ Large-scale data ingestion (~1.8M records)  
✔ Efficient group-by aggregation and hourly bucketing  
✔ High-performance geospatial rendering with datashader  
✔ Image compositing and frame interpolation  
✔ Automated end-to-end data pipeline → visualization artifact  

This mirrors real-world data engineering workflows:
Raw data → Transform → Aggregate → Render → Deliver artifact

---

## 🧠 How It Works

1. Downloads Citi Bike trip data from S3
2. Loads and processes data using pandas
3. Groups trips by hour (24-hour cycle)
4. Aggregates millions of points using datashader
5. Applies neon glow compositing over satellite basemap
6. Interpolates 120 frames for smooth animation
7. Exports optimized MP4 + GIF outputs

---

## 🛠️ Tech Stack

- pandas — data ingestion & transformation  
- datashader — scalable point aggregation  
- Pillow — image compositing & glow effects  
- contextily — satellite basemap tiles (Esri)  
- imageio — animation encoding  

---

## 📈 Why It Matters (Business Value)

Urban mobility data is widely used for:

- Demand forecasting
- Traffic pattern analytics
- Infrastructure planning
- Ride-share optimization
- Mobility anomaly detection

This project demonstrates the ability to:
• Convert large, messy datasets into insight-ready outputs  
• Handle high-volume spatial data efficiently  
• Build reproducible, automated visualization pipelines  
• Deliver analytics artifacts suitable for stakeholders  

---

## 📦 Output

| File | Description |
|------|-------------|
| city_breathing.mp4 | 10-second looping animation (~1 MB) |
| city_breathing.gif | Same animation as GIF (~62 MB) |
| city_breathing_peak.png | Peak hour thumbnail |
| city_breathing_night.png | Night thumbnail |

---

## ▶ Run Locally

```bash
pip install -r requirements.txt
python city_breathing.py
