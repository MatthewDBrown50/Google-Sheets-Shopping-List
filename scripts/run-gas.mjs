import fs from 'fs';
import path from 'path';
import { google } from 'googleapis';

const scriptId = JSON.parse(
  fs.readFileSync(path.join(process.cwd(), '.clasp.json'), 'utf8')
).scriptId;

const claspRcPath = path.join(process.env.USERPROFILE || process.env.HOME, '.clasprc.json');
const claspRc = JSON.parse(fs.readFileSync(claspRcPath, 'utf8'));
const token = claspRc.tokens?.default || claspRc.token || Object.values(claspRc.tokens || {})[0];

const oauth2Client = new google.auth.OAuth2(
  token.client_id,
  token.client_secret,
  'http://localhost:8888'
);
oauth2Client.setCredentials({
  access_token: token.access_token,
  refresh_token: token.refresh_token,
  token_type: token.token_type || 'Bearer',
});

const script = google.script({ version: 'v1', auth: oauth2Client });

const { data } = await script.scripts.run({
  scriptId,
  requestBody: {
    function: 'generateShoppingList',
    devMode: true,
  },
});

if (data.error) {
  console.error('Execution error:', JSON.stringify(data.error, null, 2));
  process.exit(1);
}

console.log('Execution completed.');
if (data.response?.result !== undefined) {
  console.log('Result:', data.response.result);
}
