# Universal Content Scraper

Web scraper that works with any website and PDFs. Real-time progress tracking.

## Setup

```bash
git clone https://github.com/fromis-9/universal-scraper.git
cd universal-scraper
python run_local.py
```

Opens http://localhost:10000

## Usage

1. Enter customer name
2. Add website URLs or upload PDFs
3. Start scraping
4. Download JSON results

## Features

- Works with JavaScript sites (React, Vue, Angular)
- PDF processing with chapter detection
- Real-time progress updates
- Fallback browser support (Chrome → Playwright → Requests)

## Deployment

**Local:**
```bash
python run_local.py
```

**Docker:**
```bash
docker build -t content-scraper .
docker run -p 10000:10000 content-scraper
```

**Cloud:** Render (requires paid plan for browser support)

## Stack

- Flask + SocketIO
- Selenium + Playwright
- Beautiful Soup
- PyMuPDF

## License

MIT 