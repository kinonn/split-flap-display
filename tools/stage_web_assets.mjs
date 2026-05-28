import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const appDir = path.join(root, "micropython", "app");
const staticDir = path.join(appDir, "static");
const templateDir = path.join(appDir, "templates");

const staticFiles = ["index.css", "index.js", "timezones.json"];

fs.mkdirSync(staticDir, { recursive: true });
fs.mkdirSync(templateDir, { recursive: true });

for (const file of staticFiles) {
    fs.copyFileSync(
        path.join(root, "build", "web", file),
        path.join(staticDir, file),
    );
}

stageTemplate("index.html", "index.tpl");
stageTemplate("settings.html", "settings.tpl");

function stageTemplate(sourceName, targetName) {
    const sourcePath = path.join(root, "src", "web", sourceName);
    const targetPath = path.join(templateDir, targetName);
    let html = fs.readFileSync(sourcePath, "utf8");

    html = html.replace(
        /<title\s+x-text="header"><\/title>/,
        "<title>{{title}}</title>",
    );
    html = html.replace('href="index.css"', 'href="/index.css"');
    html = html.replace('src="index.js"', 'src="/index.js"');
    html = html.replace(/href="index\.html"/g, 'href="/index.html"');
    html = html.replace(/href="settings\.html"/g, 'href="/settings.html"');

    fs.writeFileSync(targetPath, `{% args title="Split Flap" %}\n${html}`, "utf8");
}
