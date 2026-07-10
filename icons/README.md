# icons/

Static image assets served by the app. Everything here is copied verbatim to
the published site by `.github/workflows/deploy-pages.yml` (it ships the whole
`icons/` tree), so keep it to files the app actually uses.

```
icons/
  app/                 PWA / manifest icons
    icon-192.png         referenced by manifest.webmanifest + sw.js shell cache
    icon-512.png
  boroughs/            official borough seals — the selection-pin marker
    manhattan/
      seal.svg           vector master
      seal-48.png        raster renders (48 / 96 / 192 / 512 / 1024 px)
      seal-96.png        seal-96.png is the one the map marker loads
      seal-192.png
      seal-512.png
      seal-1024.png
    bronx/     …same layout
    brooklyn/  …
    queens/    …
    staten-island/     (Richmond County) — PNG only, no vector master
      seal.png           square master (cropped from the source gallery image)
      seal-48.png … seal-512.png
```

## Borough seals as the selection pin

When a clicked/searched point resolves to one of the five boroughs, the plain
teardrop marker is swapped for that borough's official seal. The wiring lives in
`index.html`:

- `BOROUGH_SEAL_SLUG` maps each `boroname` (from
  `data/app/borough-boundaries.json`) to its folder here.
- `boroughSealIcon(slug)` builds the Leaflet marker from
  `boroughs/<slug>/seal-96.png`.
- `applyBoroughMarker(...)` reuses the cached borough-boundary geometry and the
  shared `pointInGeometry` test to pick the borough, then upgrades the marker.
  Water / outside-NYC clicks match no borough and keep the teardrop.

To use a different seal size for the marker, change the `seal-96.png` reference
in `boroughSealIcon`.
