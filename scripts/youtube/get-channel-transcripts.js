/**
 * Fetch all videos from a YouTube channel + their transcripts via ScrapeCreators.
 *
 * Setup:
 *   npm install axios
 *   export SCRAPECREATORS_API_KEY=your_new_key   (rotate the one you pasted in chat)
 *
 * Run:
 *   node get-channel-transcripts.js
 *
 * Output:
 *   ./transcripts/<videoId>.json   (one file per video: metadata + transcript)
 *   ./transcripts/_index.json      (list of all videos processed)
 */

const axios = require('axios');
const fs = require('fs');
const path = require('path');

const API_KEY = process.env.SCRAPECREATORS_API_KEY;
if (!API_KEY) {
  console.error('Set SCRAPECREATORS_API_KEY env var first.');
  process.exit(1);
}

const HANDLE = 'essentiafoundation'; // from youtube.com/@essentiafoundation
const OUT_DIR = path.join(__dirname, 'transcripts');
const DELAY_MS = 500; // be polite to the API / rate limits

const client = axios.create({
  headers: { 'x-api-key': API_KEY },
});

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function getAllVideos() {
  let videos = [];
  let continuationToken = undefined;
  let page = 0;

  while (true) {
    page += 1;
    const params = { handle: HANDLE, sort: 'latest' };
    if (continuationToken) params.continuationToken = continuationToken;

    const { data } = await client.get(
      'https://api.scrapecreators.com/v1/youtube/channel-videos',
      { params }
    );

    if (!data.success) {
      console.error('Channel-videos request failed:', data);
      break;
    }

    videos = videos.concat(data.videos || []);
    console.log(`Page ${page}: +${data.videos?.length || 0} videos (total ${videos.length})`);

    continuationToken = data.continuationToken;
    if (!continuationToken) break;

    await sleep(DELAY_MS);
  }

  return videos;
}

async function getTranscript(videoUrl) {
  try {
    const { data } = await client.get(
      'https://api.scrapecreators.com/v1/youtube/video/transcript',
      { params: { url: videoUrl, language: 'en' } }
    );
    return data;
  } catch (err) {
    return { error: err.response?.data || err.message };
  }
}

async function main() {
  if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

  console.log(`Fetching video list for @${HANDLE}...`);
  const videos = await getAllVideos();
  console.log(`Found ${videos.length} videos total.`);

  const index = [];

  for (let i = 0; i < videos.length; i++) {
    const v = videos[i];
    console.log(`[${i + 1}/${videos.length}] ${v.id} - ${v.title}`);

    const transcript = await getTranscript(v.url);

    const record = {
      id: v.id,
      url: v.url,
      title: v.title,
      publishedTime: v.publishedTime,
      lengthSeconds: v.lengthSeconds,
      transcript,
    };

    fs.writeFileSync(
      path.join(OUT_DIR, `${v.id}.json`),
      JSON.stringify(record, null, 2)
    );

    index.push({
      id: v.id,
      title: v.title,
      url: v.url,
      transcript_available: transcript.transcript_available !== false,
    });

    await sleep(DELAY_MS);
  }

  fs.writeFileSync(
    path.join(OUT_DIR, '_index.json'),
    JSON.stringify(index, null, 2)
  );

  console.log(`Done. ${videos.length} videos processed. Output in ${OUT_DIR}`);
}

main().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});
