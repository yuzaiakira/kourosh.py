# Hello World

The smallest generated application is a vanilla project:

```sh
kourosh create hello
cd hello
```

`main.py` registers `greet(name)` and `ui/app.js` calls it through the local
bridge. Change the Python return value or the HTML form, then run `kourosh dev`
on Windows to see the native window. On Linux, use the bridge tests and
frontend build; no GUI mock is provided.
