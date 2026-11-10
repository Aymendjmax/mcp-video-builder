// Copies the woff2 files of the @fontsource packages and writes fonts.css with @font-face rules.
// Usage: node build-fonts.mjs <node_modules> <outDir>
import fs from "node:fs"; import path from "node:path";
const [nm, out] = process.argv.slice(2);
const FAM = { cairo: ["Cairo", [400, 600, 700, 800]], tajawal: ["Tajawal", [400, 500, 700, 800]], "noto-sans-arabic": ["Noto Sans Arabic", [400, 600, 700]],
  poppins: ["Poppins", [400, 500, 600, 700, 800]], inter: ["Inter", [400, 500, 600, 700, 800]], "jetbrains-mono": ["JetBrains Mono", [400, 700]] };
let css = "/* generated: local fonts, no network needed */\n"; let n = 0;
fs.mkdirSync(out, { recursive: true });
for (const [slug, [name, weights]] of Object.entries(FAM)) {
  const dir = path.join(nm, "@fontsource", slug, "files"); if (!fs.existsSync(dir)) { console.log("missing", slug); continue; }
  for (const w of weights) for (const sub of ["arabic", "latin", "latin-ext"]) {
    const f = `${slug}-${sub}-${w}-normal.woff2`; if (!fs.existsSync(path.join(dir, f))) continue;
    fs.copyFileSync(path.join(dir, f), path.join(out, f)); n++;
    const range = sub === "arabic" ? "U+0600-06FF,U+0750-077F,U+08A0-08FF,U+FB50-FDFF,U+FE70-FEFF,U+200C-200F" : sub === "latin" ? "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD" : "U+0100-02AF,U+1E00-1EFF,U+2020,U+20A0-20AB,U+20AD-20CF,U+2113,U+2C60-2C7F,U+A720-A7FF";
    css += `@font-face{font-family:"${name}";font-style:normal;font-weight:${w};font-display:block;src:url("${f}") format("woff2");unicode-range:${range};}\n`;
  }
}
fs.writeFileSync(path.join(out, "fonts.css"), css); console.log(`fonts: ${n} files, families: ${Object.values(FAM).map((x) => x[0]).join(", ")}`);
if (n < 10) { console.error("too few font files copied"); process.exit(1); }
