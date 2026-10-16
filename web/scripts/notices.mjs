import fs from 'node:fs';
import path from 'node:path';

const lock = JSON.parse(fs.readFileSync('package-lock.json', 'utf8'));
const sections = ['Third-party notices for the bundled dashboard.\n\nGenerated from production dependencies in web/package-lock.json.'];
for (const [location, entry] of Object.entries(lock.packages).sort(([a], [b]) => a.localeCompare(b, 'en'))) {
  if (!location || entry.dev || !fs.existsSync(location)) continue;
  const metadata = JSON.parse(fs.readFileSync(path.join(location, 'package.json'), 'utf8'));
  const notices = fs.readdirSync(location).filter((name) => /^(licen[cs]e|copying|notice)(\.|$|-)/i.test(name)).sort();
  const header = `${metadata.name}@${metadata.version} (${typeof metadata.license === 'string' ? metadata.license : 'see license text'})`;
  let text = notices.filter((name) => fs.statSync(path.join(location, name)).isFile()).map((name) => fs.readFileSync(path.join(location, name), 'utf8')).join('\n\n');
  if (!text) {
    const readme = fs.readdirSync(location).find((name) => /^readme\.md$/i.test(name));
    if (readme) {
      const content = fs.readFileSync(path.join(location, readme), 'utf8');
      text = content.slice(content.search(/^##? License/im));
    }
  }
  if (!text) throw new Error(`Missing third-party license text: ${metadata.name}`);
  sections.push(`${header}\n${'='.repeat(header.length)}\n\n${text.trim()}`);
}
fs.writeFileSync('../src/ryde_cli/web/THIRD_PARTY_NOTICES.txt', (sections.join('\n\n') + '\n').replace(/\r\n/g, '\n').replace(/[ \t]+$/gm, ''));
