import fs from 'node:fs';
import path from 'node:path';
import sharp from 'sharp';

const EXTENSIONS = new Set(['.jpg', '.jpeg', '.png', '.webp', '.gif', '.avif', '.tiff', '.bmp']);
const THUMB_WIDTH = 400;

function* walk(dir) {
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    if (entry.name.startsWith('.')) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      yield* walk(full);
    } else if (entry.isFile() && EXTENSIONS.has(path.extname(entry.name).toLowerCase())) {
      yield full;
    }
  }
}

export function thumbPath(dataDir, imageId) {
  return path.join(dataDir, 'thumbs', `${imageId}.webp`);
}

async function dominantColor(instance) {
  const { dominant } = await instance.stats();
  const hex = (n) => n.toString(16).padStart(2, '0');
  return `#${hex(dominant.r)}${hex(dominant.g)}${hex(dominant.b)}`;
}

// Scans every registered folder: inserts new files, refreshes changed ones
// (mtime/size mismatch), and prunes DB rows whose files disappeared.
export async function scanAll(db, dataDir, onProgress = () => {}) {
  fs.mkdirSync(path.join(dataDir, 'thumbs'), { recursive: true });

  const folders = db.prepare('SELECT * FROM folders').all();
  const known = new Map(
    db.prepare('SELECT id, path, mtime, size FROM images').all().map((r) => [r.path, r])
  );

  const insert = db.prepare(`
    INSERT INTO images (folder_id, path, filename, width, height, size, mtime, color, indexed_at)
    VALUES (@folder_id, @path, @filename, @width, @height, @size, @mtime, @color, @indexed_at)
    ON CONFLICT(path) DO UPDATE SET
      width=excluded.width, height=excluded.height, size=excluded.size,
      mtime=excluded.mtime, color=excluded.color, indexed_at=excluded.indexed_at
  `);
  const getId = db.prepare('SELECT id FROM images WHERE path = ?');

  const seen = new Set();
  let added = 0;
  let updated = 0;

  for (const folder of folders) {
    for (const file of walk(folder.path)) {
      seen.add(file);
      let stat;
      try {
        stat = fs.statSync(file);
      } catch {
        continue;
      }
      const prev = known.get(file);
      if (prev && prev.mtime === Math.floor(stat.mtimeMs) && prev.size === stat.size) continue;

      try {
        const image = sharp(file, { failOn: 'truncated' });
        const meta = await image.metadata();
        const color = await dominantColor(sharp(file));
        insert.run({
          folder_id: folder.id,
          path: file,
          filename: path.basename(file),
          width: meta.width ?? 0,
          height: meta.height ?? 0,
          size: stat.size,
          mtime: Math.floor(stat.mtimeMs),
          color,
          indexed_at: Date.now(),
        });
        const { id } = getId.get(file);
        await sharp(file)
          .resize({ width: THUMB_WIDTH, withoutEnlargement: true })
          .webp({ quality: 80 })
          .toFile(thumbPath(dataDir, id));
        prev ? updated++ : added++;
        onProgress({ added, updated, current: file });
      } catch (err) {
        console.warn(`skip ${file}: ${err.message}`);
      }
    }
  }

  // Prune rows for files that no longer exist on disk.
  let removed = 0;
  const del = db.prepare('DELETE FROM images WHERE id = ?');
  for (const [file, row] of known) {
    if (!seen.has(file)) {
      del.run(row.id);
      fs.rmSync(thumbPath(dataDir, row.id), { force: true });
      removed++;
    }
  }

  return { added, updated, removed };
}
