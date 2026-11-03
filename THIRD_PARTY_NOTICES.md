# Third-party notices

Demos is under the PolyForm Noncommercial License 1.0.0 (see `LICENSE`). The parts below come from other people and keep their own licenses.

## Code from the Expo starter

The app was started from the `create-expo-app` template. `app/index.ts` and `app/.gitignore` still come from it, under this license:

```
The MIT License (MIT)

Copyright (c) 2015-present 650 Industries, Inc. (aka Expo)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Fonts

Bricolage Grotesque and DM Mono are under the SIL Open Font License 1.1. The app gets them from the `@expo-google-fonts` packages, and the project page loads them from Google Fonts. No font files are kept in this repo.

## Dependencies

Nothing else is copied into the repo. These are installed by `npm install` and `uv sync`, each under its own license:

| Package | License |
| --- | --- |
| expo and the expo-* modules, react, react-native, react-native-svg, react-native-safe-area-context, expo-speech-recognition | MIT |
| @expo-google-fonts/bricolage-grotesque, @expo-google-fonts/dm-mono | MIT (code) and OFL-1.1 (fonts) |
| fastapi, pydantic, pydantic-settings | MIT |
| anthropic, python-multipart | Apache-2.0 |
| httpx, scikit-learn, uvicorn | BSD-3-Clause |
| psycopg | LGPL-3.0 |

The lock files (`app/package-lock.json`, `backend/uv.lock`) have the full list.
