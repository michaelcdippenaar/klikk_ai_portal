# PAW Embedding — Skill / Reference

This document describes how the Klikk AI Portal embeds IBM Planning Analytics Workspace (PAW) content and communicates with it using **iframe** embedding and the **HTML5 postMessage API**. It aligns with the IBM TechXchange / PAW UI API patterns.

**Note:** IBM’s “Embedding visualization code” topic in the docs often refers to **Cognos Analytics** (dashboard Embed icon, `CognosDashboardApi.js`, CORS on Cognos). That is a different product. This document is only for **Planning Analytics Workspace (PAW)**.

---

## 1. Embedding PAW content

PAW books or widgets are embedded in the host application via an **iframe**.

### URL formats

- **Cube viewer / dimension editor / set editor** (PAW UI API):
  - `https://<PAW_HOST>:<PORT>/ui?type=cube-viewer&server=<TM1_SERVER>&cube=<CUBE>&view=<VIEW>`
  - In this portal we use a same-origin proxy: `/paw/ui?type=...` so the iframe is same-origin and avoids CORS for the initial load.
- **Book** (dashboard-style embed):
  - `https://<PAW_URL>/#/book/<BookID>?embed=true`
  - Or via PAW UI API: `/?perspective=dashboard&path=/shared/<Book>&embed=true`

### Security (CSP)

The PAW administrator must add the **parent application’s domain** to the **Content Security Policy (CSP)** in PAW so the frame is allowed to load. Without this, the iframe may be blocked by the browser.

---

## 2. Sending messages (parent → PAW)

The parent uses `postMessage` to send commands to the embedded PAW frame (e.g. dimension sync, navigation, redraw).

### Target and origin

- **Target:** `pawFrame.contentWindow` (the iframe’s window).
- **Origin:** `targetOrigin` must be the PAW server origin (e.g. `https://your-paw-server-url.com`) for security. In this portal we use the same origin as the page when using the `/paw/` proxy.

### Message shapes used in this portal (PAW UI API)

- **Subscribe** to events (e.g. member selection, commands):
  ```js
  { type: 'subscribe', eventName: 'tm1mdv:memberSelect', eventPayload: { name: '...' } }
  ```
- **Trigger** an action (e.g. redraw):
  ```js
  { type: 'trigger', eventName: 'tm1mdv:redraw' }
  ```

### Dimension sync (parent → PAW)

Some PAW integrations use an **execute/sync** pattern to push dimension context into the book:

```js
const message = {
  type: 'execute',
  eventName: 'sync',
  eventPayload: {
    book: [
      {
        serverName: "TM1_Database_Name",
        hierarchyID: "[Dimension].[Hierarchy]",
        memberID: "[Dimension].[Hierarchy].[Element_Name]",
        alias: "Optional_Alias"
      }
    ]
  }
};
pawFrame.contentWindow.postMessage(message, targetOrigin);
```

The portal currently uses **subscribe** and **trigger**; the **sync** pattern can be added where PAW supports it (see official PAW UI API and IBM Community for exact payloads).

---

## 3. Receiving messages (PAW → parent)

The parent listens for events from the embedded PAW frame.

### Security

**Always verify `event.origin`** before using `event.data`.

```js
window.addEventListener('message', (event) => {
  if (event.origin !== 'https://your-paw-server-url.com') return;

  console.log('Received from PAW:', event.data);

  if (event.data.eventName === 'sync') {
    const payload = event.data.eventPayload;
    // Handle synchronization event
  }
}, false);
```

### Message types used in this portal

- **onWidgetLoaded** — `data.type === 'onWidgetLoaded'`: widget is ready; we then subscribe to events and trigger redraw.
- **on** — `data.type === 'on'`: named event from PAW; `data.eventName` (e.g. `tm1mdv:memberSelect`), `data.eventPayload` (e.g. cube, server, queryState, member IDs). We push this into the widget-context store for the agent.

---

## 4. PAW local: CORS

For **PAW Local**, the PAW server must allow the portal’s origin in **CORS** so that the parent can communicate with PAW (and so PAW can respond to postMessage where applicable). Without this, widget loading or postMessage may fail.

- **PAW on Cloud:** iframe embedding is not supported; the UI API is for same-tab use.
- **PAW Local:** enable CORS for the portal origin (e.g. `http://192.168.1.235:8000` or your production domain) in PAW configuration, then restart/apply.

Exact steps depend on PAW/TM1 version; see IBM docs for “Configure parameters” or “CORS” for Planning Analytics Workspace.

---

## 5. Official references

- **IBM Planning Analytics Workspace UI API (GitHub):**  
  https://ibm.github.io/planninganalyticsapi/  
  Primary reference for embed URLs, postMessage protocol, and event schemas.
- **IBM Documentation — Planning Analytics Workspace:**  
  Administration and user guides.
- **IBM Community / TechXchange:**  
  Advanced messaging payloads and sync examples.

---

## 6. Cognos “Embedding visualization code” (different product)

The IBM topic **“Embedding visualization code”** refers to **Cognos Analytics** (on‑prem or Cloud Hosted), not PAW:

- User clicks the **Embed** icon in the dashboard toolbar and copies a snippet.
- The snippet loads `CognosDashboardApi.js` and embeds a Cognos dashboard.
- If the site is on a different domain than Cognos, **CORS must be enabled on the Cognos server** (e.g. `Access-Control-Allow-Origin`, `cookieSameSite`, etc. per IBM CORS docs).

This portal does **not** use the Cognos Embed flow; it uses **PAW** and the PAW UI API as described above.
