import express from 'express';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { openDb } from './lib/db.js';
import { scanAll, thumbPath } from './lib/indexer.js';
import { autoTag, taggerInfo } from './lib/tagger.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = process.env.MIRU_DATA ?? path.join(__dirname, 'data');
const PORT = Number(process.env.PORT ?? 3777);

const db = openDb(DATA_DIR);
const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Folders passed as CLI args are registered on startup: `node server.js ~/Pictures`
for (const arg of process.argv.slice(2)) {
  const abs = path.resolve(arg);
  if (fs.existsSync(abs)) {
    db.prepare('INSERT OR IGNORE INTO folders (path) VALUES (?)').run(abs);
  } else {
    console.warn(`folder not found, skipping: ${abs}`);
  }
}

let scanning = false;
async function runScan() {
  if (scanning) return null;
  scanning = true;
  try {
    return await scanAll(db, DATA_DIR);
  } finally {
    scanning = false;
  }
}

// ---- API ----

app.get('/api/folders', (req, res) => {
  res.json(db.prepare('SELECT * FROM folders ORDER BY path').all());
});

app.post('/api/folders', async (req, res) => {
  const abs = path.resolve(String(req.body.path ?? ''));
  if (!fs.existsSync(abs) || !fs.statSync(abs).isDirectory()) {
    return res.status(400).json({ error: `not a directory: ${abs}` });
  }
  db.prepare('INSERT OR IGNORE INTO folders (path) VALUES (?)').run(abs);
  const result = await runScan();
  res.json({ ok: true, scan: result });
});

app.delete('/api/folders/:id', (req, res) => {
  const folder = db.prepare('SELECT * FROM folders WHERE id = ?').get(req.params.id);
  if (!folder) return res.status(404).json({ error: 'not found' });
  const ids = db.prepare('SELECT id FROM images WHERE folder_id = ?').all(folder.id);
  db.prepare('DELETE FROM folders WHERE id = ?').run(folder.id);
  for (const { id } of ids) fs.rmSync(thumbPath(DATA_DIR, id), { force: true });
  res.json({ ok: true });
});

app.post('/api/scan', async (req, res) => {
  const result = await runScan();
  if (!result) return res.status(409).json({ error: 'scan already running' });
  res.json(result);
});

app.get('/api/images', (req, res) => {
  const { q, tag, minRating, rejected, sort, offset, limit } = req.query;
  const where = [];
  const params = {};

  if (q) {
    where.push(`(i.filename LIKE @q OR EXISTS (
      SELECT 1 FROM image_tags it JOIN tags t ON t.id = it.tag_id
      WHERE it.image_id = i.id AND t.name LIKE @q))`);
    params.q = `%${q}%`;
  }
  if (tag) {
    where.push(`EXISTS (SELECT 1 FROM image_tags it JOIN tags t ON t.id = it.tag_id
      WHERE it.image_id = i.id AND t.name = @tag)`);
    params.tag = tag;
  }
  if (minRating) {
    where.push('i.rating >= @minRating');
    params.minRating = Number(minRating);
  }
  // Rejected images are hidden unless explicitly requested.
  where.push(rejected === '1' ? 'i.rejected = 1' : 'i.rejected = 0');

  const sorts = {
    newest: 'i.mtime DESC',
    oldest: 'i.mtime ASC',
    rating: 'i.rating DESC, i.mtime DESC',
    name: 'i.filename COLLATE NOCASE ASC',
    random: 'i.id * 2654435761 % 4294967296', // stable pseudo-shuffle
  };
  const orderBy = sorts[sort] ?? sorts.newest;
  const whereSql = where.length ? `WHERE ${where.join(' AND ')}` : '';

  const total = db.prepare(`SELECT COUNT(*) AS n FROM images i ${whereSql}`).get(params).n;
  const rows = db
    .prepare(`
      SELECT i.id, i.filename, i.width, i.height, i.rating, i.rejected, i.color, i.mtime, i.size,
        (SELECT json_group_array(t.name) FROM image_tags it JOIN tags t ON t.id = it.tag_id
         WHERE it.image_id = i.id) AS tags
      FROM images i ${whereSql}
      ORDER BY ${orderBy}
      LIMIT @limit OFFSET @offset`)
    .all({ ...params, limit: Math.min(Number(limit ?? 200), 500), offset: Number(offset ?? 0) });

  for (const r of rows) r.tags = JSON.parse(r.tags);
  res.json({ total, images: rows });
});

app.patch('/api/images/:id', (req, res) => {
  const image = db.prepare('SELECT id FROM images WHERE id = ?').get(req.params.id);
  if (!image) return res.status(404).json({ error: 'not found' });
  const { rating, rejected } = req.body;
  if (rating !== undefined) {
    const r = Number(rating);
    if (!Number.isInteger(r) || r < 0 || r > 5) return res.status(400).json({ error: 'rating must be 0-5' });
    db.prepare('UPDATE images SET rating = ? WHERE id = ?').run(r, image.id);
  }
  if (rejected !== undefined) {
    db.prepare('UPDATE images SET rejected = ? WHERE id = ?').run(rejected ? 1 : 0, image.id);
  }
  res.json({ ok: true });
});

app.post('/api/images/:id/tags', (req, res) => {
  const image = db.prepare('SELECT id FROM images WHERE id = ?').get(req.params.id);
  if (!image) return res.status(404).json({ error: 'not found' });
  const name = String(req.body.tag ?? '').trim().toLowerCase();
  if (!name) return res.status(400).json({ error: 'empty tag' });
  db.prepare('INSERT OR IGNORE INTO tags (name) VALUES (?)').run(name);
  const { id: tagId } = db.prepare('SELECT id FROM tags WHERE name = ?').get(name);
  db.prepare('INSERT OR IGNORE INTO image_tags (image_id, tag_id) VALUES (?, ?)').run(image.id, tagId);
  res.json({ ok: true });
});

app.delete('/api/images/:id/tags/:tag', (req, res) => {
  db.prepare(`
    DELETE FROM image_tags WHERE image_id = ?
    AND tag_id = (SELECT id FROM tags WHERE name = ?)`)
    .run(req.params.id, req.params.tag);
  db.prepare('DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM image_tags)').run();
  res.json({ ok: true });
});

function addTags(imageId, tags) {
  const insertTag = db.prepare('INSERT OR IGNORE INTO tags (name) VALUES (?)');
  const getTag = db.prepare('SELECT id FROM tags WHERE name = ?');
  const link = db.prepare('INSERT OR IGNORE INTO image_tags (image_id, tag_id) VALUES (?, ?)');
  for (const name of tags) {
    insertTag.run(name);
    link.run(imageId, getTag.get(name).id);
  }
}

app.get('/api/tagger', (req, res) => {
  res.json(taggerInfo());
});

app.post('/api/images/:id/autotag', async (req, res) => {
  const image = db.prepare('SELECT id, path FROM images WHERE id = ?').get(req.params.id);
  if (!image) return res.status(404).json({ error: 'not found' });
  try {
    const tags = await autoTag(image.path);
    addTags(image.id, tags);
    res.json({ tags });
  } catch (err) {
    res.status(502).json({ error: err.message, ...taggerInfo() });
  }
});

// Batch-tag images that have no tags yet. Sequential on purpose — local
// LLMs and CLI agents don't like concurrent invocations.
app.post('/api/autotag', async (req, res) => {
  const limit = Math.min(Number(req.body?.limit ?? 20), 200);
  const untagged = db.prepare(`
    SELECT id, path FROM images
    WHERE rejected = 0 AND id NOT IN (SELECT image_id FROM image_tags)
    ORDER BY mtime DESC LIMIT ?`).all(limit);
  const results = { tagged: 0, failed: 0, errors: [] };
  for (const image of untagged) {
    try {
      addTags(image.id, await autoTag(image.path));
      results.tagged++;
    } catch (err) {
      results.failed++;
      if (results.errors.length < 3) results.errors.push(err.message);
    }
  }
  res.json({ ...results, processed: untagged.length });
});

app.get('/api/tags', (req, res) => {
  res.json(db.prepare(`
    SELECT t.name, COUNT(it.image_id) AS count
    FROM tags t JOIN image_tags it ON it.tag_id = t.id
    GROUP BY t.id ORDER BY count DESC, t.name`).all());
});

// ---- image serving ----

app.get('/thumbs/:id.webp', (req, res) => {
  const file = thumbPath(DATA_DIR, Number(req.params.id));
  if (!fs.existsSync(file)) return res.status(404).end();
  res.sendFile(file);
});

app.get('/files/:id', (req, res) => {
  const row = db.prepare('SELECT path FROM images WHERE id = ?').get(req.params.id);
  if (!row || !fs.existsSync(row.path)) return res.status(404).end();
  res.sendFile(row.path);
});

app.listen(PORT, async () => {
  console.log(`miru running at http://localhost:${PORT}`);
  const result = await runScan();
  if (result) console.log(`scan done: +${result.added} ~${result.updated} -${result.removed}`);
});
