/**
 * LinkedIn OAuth 2.0 Authorization Code Flow — One-Time Setup
 *
 * This script helps you obtain a LinkedIn access token and person URN.
 * Run it once, follow the browser steps, then paste the values into .env.
 *
 * Usage:
 *   node linkedin_auth.js
 *
 * Steps:
 *   1. Run this script
 *   2. Open the URL it prints in your browser
 *   3. Sign in to LinkedIn and authorize the app
 *   4. You'll be redirected to localhost:3000/callback
 *   5. The script exchanges the code for an access token
 *   6. Copy the LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN into .env
 *   7. Restart the MCP server
 *
 * Required .env variables (already set):
 *   LINKEDIN_CLIENT_ID
 *   LINKEDIN_CLIENT_SECRET
 *   LINKEDIN_REDIRECT_URI=http://localhost:3000/callback
 */

import 'dotenv/config';
import http from 'http';
import { URL } from 'url';

const CLIENT_ID = process.env.LINKEDIN_CLIENT_ID;
const CLIENT_SECRET = process.env.LINKEDIN_CLIENT_SECRET;
const REDIRECT_URI = process.env.LINKEDIN_REDIRECT_URI || 'http://localhost:3000/callback';
const PORT = 3000;

// Scopes: w_member_social (posting) + openid/profile (person URN detection)
// Requires both "Share on LinkedIn" and "Sign In with LinkedIn using OpenID Connect" products
const SCOPES = ['openid', 'profile', 'w_member_social'];

if (!CLIENT_ID || !CLIENT_SECRET) {
  console.error('ERROR: Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in .env first');
  process.exit(1);
}

// Build the authorization URL
const authUrl = new URL('https://www.linkedin.com/oauth/v2/authorization');
authUrl.searchParams.set('response_type', 'code');
authUrl.searchParams.set('client_id', CLIENT_ID);
authUrl.searchParams.set('redirect_uri', REDIRECT_URI);
authUrl.searchParams.set('scope', SCOPES.join(' '));
authUrl.searchParams.set('state', 'ai-employee-auth-' + Date.now());

console.log('='.repeat(60));
console.log('LinkedIn OAuth 2.0 — One-Time Setup');
console.log('='.repeat(60));
console.log();
console.log('Step 1: Open this URL in your browser:');
console.log();
console.log(authUrl.toString());
console.log();
console.log('Step 2: Sign in to LinkedIn and authorize the app');
console.log('Step 3: Wait for the redirect — this script will catch it');
console.log();
console.log(`Listening on http://localhost:${PORT} ...`);
console.log();

/**
 * Exchange the authorization code for an access token.
 */
async function exchangeCodeForToken(code) {
  const tokenUrl = 'https://www.linkedin.com/oauth/v2/accessToken';

  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    code: code,
    client_id: CLIENT_ID,
    client_secret: CLIENT_SECRET,
    redirect_uri: REDIRECT_URI,
  });

  const response = await fetch(tokenUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Token exchange failed (${response.status}): ${errorText}`);
  }

  return response.json();
}

/**
 * Get the authenticated user's profile (person URN + name).
 * Tries /v2/userinfo (openid scope) first, then /v2/me (profile scope).
 * Returns null if none work.
 */
async function getUserProfile(accessToken) {
  const endpoints = [
    'https://api.linkedin.com/v2/userinfo',
    'https://api.linkedin.com/v2/me',
  ];

  for (const url of endpoints) {
    try {
      const response = await fetch(url, {
        headers: { 'Authorization': `Bearer ${accessToken}` },
      });
      if (response.ok) {
        const data = await response.json();
        data._source = url;
        return data;
      }
    } catch (_) {
      // Try next endpoint
    }
  }

  return null;
}

// Start the local callback server
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);

  if (url.pathname !== '/callback') {
    res.writeHead(404);
    res.end('Not found');
    return;
  }

  const code = url.searchParams.get('code');
  const error = url.searchParams.get('error');

  if (error) {
    const desc = url.searchParams.get('error_description') || 'Unknown error';
    console.error(`\nERROR: LinkedIn denied authorization: ${error} — ${desc}`);
    res.writeHead(400, { 'Content-Type': 'text/html' });
    res.end(`<h1>Authorization Failed</h1><p>${error}: ${desc}</p>`);
    process.exit(1);
  }

  if (!code) {
    res.writeHead(400, { 'Content-Type': 'text/html' });
    res.end('<h1>Error</h1><p>No authorization code received</p>');
    return;
  }

  console.log('Authorization code received! Exchanging for access token...');
  console.log();

  try {
    // Exchange code for token
    const tokenData = await exchangeCodeForToken(code);
    const accessToken = tokenData.access_token;
    const expiresIn = tokenData.expires_in;

    console.log('Access token obtained!');
    console.log(`Expires in: ${Math.round(expiresIn / 86400)} days (${expiresIn} seconds)`);
    console.log();

    // Try to get user profile for person URN
    const profile = await getUserProfile(accessToken);
    let personUrn = '';
    let name = 'Unknown';
    let rawSub = '';

    if (profile) {
      // /v2/userinfo returns 'sub', /v2/me returns 'id'
      rawSub = profile.sub || profile.id;
      personUrn = `urn:li:person:${rawSub}`;
      name = profile.name
        || (profile.localizedFirstName ? `${profile.localizedFirstName} ${profile.localizedLastName || ''}` : 'Unknown');
      console.log(`Profile source: ${profile._source}`);
      console.log(`Raw profile data: ${JSON.stringify(profile, null, 2)}`);
    }

    console.log('='.repeat(60));
    console.log('SUCCESS! Copy these values into your .env file:');
    console.log('='.repeat(60));
    console.log();
    console.log(`LINKEDIN_ACCESS_TOKEN=${accessToken}`);
    if (personUrn) {
      console.log(`LINKEDIN_PERSON_URN=${personUrn}`);
      console.log();
      console.log(`Profile: ${name}`);
    } else {
      console.log();
      console.log('NOTE: Could not auto-detect Person URN (profile scope not available).');
      console.log('To find your Person URN manually:');
      console.log('  1. Go to https://www.linkedin.com/in/me');
      console.log('  2. Your profile URL contains your vanity name');
      console.log('  3. Or use this token to call: GET https://api.linkedin.com/v2/me');
      console.log('  4. Set LINKEDIN_PERSON_URN=urn:li:person:<your-id> in .env');
    }
    console.log(`Expires: ${new Date(Date.now() + expiresIn * 1000).toISOString()}`);
    console.log();
    console.log('After updating .env, restart the MCP server to use live LinkedIn posting.');
    console.log('='.repeat(60));

    // Send success response to browser
    const urnNote = personUrn
      ? `<p>Person URN: <code>${personUrn}</code></p>`
      : `<p style="color: orange;">Person URN could not be auto-detected. Check terminal for instructions.</p>`;

    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end(`
      <html>
      <body style="font-family: Arial; max-width: 600px; margin: 50px auto; text-align: center;">
        <h1 style="color: #0077B5;">LinkedIn Connected!</h1>
        <p>Hello, <strong>${name}</strong></p>
        ${urnNote}
        <p>Your access token has been printed in the terminal.</p>
        <h3>Next Steps:</h3>
        <ol style="text-align: left;">
          <li>Go back to the terminal</li>
          <li>Copy <code>LINKEDIN_ACCESS_TOKEN</code> (and <code>LINKEDIN_PERSON_URN</code> if shown)</li>
          <li>Paste them into <code>mcp_server/.env</code></li>
          <li>Restart the MCP server</li>
        </ol>
        <p style="color: #666;">You can close this tab now.</p>
      </body>
      </html>
    `);

    // Close the server after a short delay
    setTimeout(() => {
      server.close();
      process.exit(0);
    }, 2000);

  } catch (err) {
    console.error(`\nERROR: ${err.message}`);
    res.writeHead(500, { 'Content-Type': 'text/html' });
    res.end(`<h1>Error</h1><p>${err.message}</p>`);
  }
});

server.listen(PORT, () => {
  // Server is ready
});
