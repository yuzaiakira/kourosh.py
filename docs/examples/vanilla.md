# Vanilla JavaScript application

The vanilla template has no Node.js dependency:

```sh
kourosh create vanilla-app
cd vanilla-app
kourosh doctor
```

Edit `ui/index.html`, `ui/style.css`, and `ui/app.js`. Keep `ui/kourosh.js`
before application scripts. Register Python methods in `main.py` and handle
structured errors in the Promise rejection path. The static project can run
with `kourosh run` after the native Windows host is available.
