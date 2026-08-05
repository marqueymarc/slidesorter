# SlideSorter website

This is the static marketing site for SlideSorter. It contains no media,
catalog, thumbnails, state profile, or action history.

`assets/` contains two cropped, dark-mode SlideSorter gallery captures: a
non-identifying scenic picture page and one non-identifying waterfall video
card. The captures were resized and stripped of embedded metadata for this
site. These files become public when the site is deployed; never add private
family media, collection state, or an unreviewed gallery capture here.

Preview it locally:

```sh
cd site
python3 -m http.server 8000
```

Then open `http://127.0.0.1:8000`.

The GitHub Actions workflow in `../.github/workflows/pages.yml` publishes this
directory to GitHub Pages after Pages is enabled for the repository and a
commit reaches `main`.
