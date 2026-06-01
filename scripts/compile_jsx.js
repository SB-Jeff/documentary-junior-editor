// Build-time JSX → JS compiler for build_quotes_viewer.py.
//
// Reads JSX source on stdin, writes plain JS (React.createElement calls) to
// stdout. Uses the vendored @babel/standalone so the build needs no network
// and no npm install — only a Node runtime. The compiled output is inlined
// into the viewer HTML, so the artifact never loads Babel or any CDN script.
const path = require("path");
const Babel = require(path.join(__dirname, "vendor", "babel.min.js"));

let src = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (d) => { src += d; });
process.stdin.on("end", () => {
  try {
    const out = Babel.transform(src, {
      presets: [["react", { runtime: "classic" }]],
      compact: false,
    }).code;
    process.stdout.write(out);
  } catch (e) {
    process.stderr.write(String((e && e.stack) || e));
    process.exit(1);
  }
});
