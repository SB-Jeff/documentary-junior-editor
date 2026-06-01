# Vendored runtime libraries

Inlined into the generated quote-viewer HTML by `build_quotes_viewer.py` so the
artifact is genuinely self-contained — no CDN, no runtime Babel, renders offline
and inside sandboxed webviews (e.g. the Cowork artifact frame).

- `react.production.min.js`      — React 18.3.1 UMD (inlined into output)
- `react-dom.production.min.js`  — ReactDOM 18.3.1 UMD (inlined into output)
- `babel.min.js`                 — @babel/standalone 7.26.4 (BUILD-TIME ONLY;
                                   used by `compile_jsx.js` to transpile the
                                   JSX template to plain JS; never shipped)

Re-vendor:
  curl -sL https://unpkg.com/react@18.3.1/umd/react.production.min.js     -o scripts/vendor/react.production.min.js
  curl -sL https://unpkg.com/react-dom@18.3.1/umd/react-dom.production.min.js -o scripts/vendor/react-dom.production.min.js
  curl -sL https://unpkg.com/@babel/standalone@7.26.4/babel.min.js        -o scripts/vendor/babel.min.js
