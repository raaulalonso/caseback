// Where each phone lands in the render, 0 to 1 from the top left. Written by tools/app_renders/render_all.py; do not edit.
export const appRenders = {
  today: { width: 1784, height: 1414, phones: [{ shot: "today_night", x: 0.2088, top: 0.1270, bottom: 0.9380 }, { shot: "today_sheet", x: 0.7912, top: 0.1270, bottom: 0.9380 }, { shot: "today_now", x: 0.5000, top: 0.0487, bottom: 0.9341 }] },
  trends: { width: 1670, height: 1782, phones: [{ shot: "trends_readiness", x: 0.2551, top: 0.0407, bottom: 0.7637 }, { shot: "trends_scrub", x: 0.7493, top: 0.1462, bottom: 0.9422 }] },
  device: { width: 1919, height: 1530, phones: [{ shot: "device_health", x: 0.1825, top: 0.0436, bottom: 0.7266 }, { shot: "device", x: 0.4847, top: 0.1060, bottom: 0.8276 }, { shot: "device_data", x: 0.8225, top: 0.1756, bottom: 0.9407 }] },
  widgets: { width: 1930, height: 1254, phones: [{ shot: "widgets_home_fresh", x: 0.1815, top: 0.0544, bottom: 0.9364 }, { shot: "widgets_home_day", x: 0.5061, top: 0.0544, bottom: 0.9364 }, { shot: "widgets_home_days", x: 0.8306, top: 0.0544, bottom: 0.9364 }] },
} as const;
