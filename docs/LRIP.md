Cloudinary API and credentials
- For server-side uploads or API calls, set the following env vars in your Render environment (these are read by `app.config` but API secrets are NOT exposed to templates):
   - `CLOUDINARY_CLOUD_NAME` — your Cloudinary cloud name
   - `CLOUDINARY_API_KEY` — Cloudinary API key (server-side only)
   - `CLOUDINARY_API_SECRET` — Cloudinary API secret (server-side only)
   - Optionally `CLOUDINARY_BASE_URL` — override base delivery URL if you prefer a custom domain

The app derives `CLOUDINARY_BASE_URL` automatically when `CLOUDINARY_CLOUD_NAME` is set (value: `https://res.cloudinary.com/<cloud-name>/image/upload`).
LRIP (Low-Resolution Image Placeholder) Integration

Overview
- This documents how to add tiny Base64 placeholders and configure Cloudinary high-res URLs for background images.

Files added
- `backend/app/static/css/bg.css` - CSS for placeholder and main image layers.
- `backend/app/static/js/bg-swap.js` - JavaScript that preloads the high-res image and swaps it in.
- `backend/app/templates/base.html` - now includes a background container and pulls `CLOUDINARY_BG_URL` from the template context.
- `backend/app/__init__.py` - context processor exposes `CLOUDINARY_BG_URL` to templates.

How it works
1. Add your tiny placeholder (20px wide, low-quality JPG) and convert to Base64 (many online tools). The output should look like `data:image/jpeg;base64,/9j/4AAQSkZJRg...`.
2. In pages where you want a background, set the `data-placeholder` value. There are two approaches:

  a) Global background (simple):
     - Set the Render/hosting environment variable `CLOUDINARY_BG_URL` to the Cloudinary URL for the image (example: `https://res.cloudinary.com/your-cloud/image/upload/v12345/your-image.jpg`).
     - Optionally add `CLOUDINARY_PLACEHOLDER` to your Flask environment (or modify the template) to provide a default base64 placeholder string.

  b) Per-service or per-page backgrounds:
     - Instead of relying on the single `CLOUDINARY_BG_URL`, set a template variable `CLOUDINARY_PLACEHOLDER` and/or override the container in page templates.
     - Example in a page template:

```html
{%- set placeholder = 'data:image/jpeg;base64,/9j/4AAQSkZJRg...' -%}
{%- set cloud = 'https://res.cloudinary.com/your-cloud/image/upload/v12345/service-bg.jpg' -%}
<div id="lrip-bg" data-cloudinary="{{ cloud }}" data-placeholder="{{ placeholder }}" data-transform="f_auto,q_auto"></div>
```

Notes on Cloudinary transformations
- The JS appends `tr=f_auto,q_auto` by default. You can add additional options via `data-transform` on the container (e.g., `dpr_auto,c_fill,w_1600`)
- Example: `data-transform="f_auto,q_auto,w_1600,c_fill"`.

CSP and security
- `Content-Security-Policy` in `app.config` allows `img-src` from `data:` and https: which is required for base64 placeholders and remote Cloudinary images. If you tighten CSP, ensure `img-src` allows your Cloudinary domain and `data:`.

Adding service images
- For each service page/template, add the container with `data-cloudinary` pointing to the Cloudinary URL for that service, and `data-placeholder` set to its Base64 20px placeholder.

Example per-service snippet (place inside a page template):

```html
{%- set placeholder = 'data:image/jpeg;base64,/9j/4AAQSkZJRg...' -%}
{%- set cloud = 'https://res.cloudinary.com/your-cloud/image/upload/v12345/service-bg.jpg' -%}
<div id="lrip-bg" data-cloudinary="{{ cloud }}" data-placeholder="{{ placeholder }}" data-transform="f_auto,q_auto"></div>
```

Testing locally
- Locally, set the env var before running Flask, or start with an overridden template value.

Example (PowerShell):

```powershell
$env:CLOUDINARY_BG_URL = 'https://res.cloudinary.com/.../bg.jpg'
flask run
```

Next steps
- I can add a helper Jinja macro to simplify per-page/service placeholders and examples integrated into `backend/app/templates/services.html`.
- If you provide the sample images, I can generate 20px placeholders and embed them directly in the service templates.
