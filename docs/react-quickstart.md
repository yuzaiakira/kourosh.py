# React quick start

Create a React or React+TypeScript project:

```sh
kourosh create react-demo --ui react
kourosh create react-ts-demo --ui react --typescript
cd react-demo
npm install
```

Run `npm run typecheck` in the TypeScript template.

The generated project contains `main.py`, a `vite.config` file, `src/`, a
`public/kourosh-bridge.js` bootstrap, a local `vendor/@kourosh/sdk`, and a
real `greet` call from the React component to the registered Python function.
The Python entrypoint points production execution at `dist/index.html`.

Use `kourosh dev` on Windows to start Vite on loopback and launch the native
host. On Linux, the command starts and validates Vite, then reports that the
WebView2 host cannot run; it does not launch a mock window.
