//! Windows-first WRY host. Linux builds retain a clear unsupported-platform
//! executable so portable bridge/Python tests can run in cloud environments.

#[cfg(not(windows))]
fn main() {
    eprintln!("kourosh-host requires Windows WebView2; portable bridge tests remain supported");
}

#[cfg(windows)]
fn main() -> Result<(), Box<dyn std::error::Error>> {
    run_windows_host()
}

#[cfg(windows)]
fn run_windows_host() -> Result<(), Box<dyn std::error::Error>> {
    use kourosh_bridge::{AsyncDispatcher, BridgeError, RpcResponse, TRUSTED_ORIGIN};
    use kourosh_python::PythonRuntime;
    use std::borrow::Cow;
    use std::sync::Arc;
    use std::thread;
    use std::time::Duration;
    use tao::event::{Event, WindowEvent};
    use tao::event_loop::{ControlFlow, EventLoopBuilder};
    use tao::window::WindowBuilder;
    use wry::http::{header::CONTENT_TYPE, Response};
    use wry::{WebViewBuilder, WebViewBuilderExtWindows};

    enum UserEvent {
        Response(RpcResponse),
    }

    let event_loop = EventLoopBuilder::<UserEvent>::with_user_event().build();
    let proxy = event_loop.create_proxy();
    let window = WindowBuilder::new()
        .with_title("Kourosh.py")
        .build(&event_loop)?;
    let runtime = Arc::new(PythonRuntime::new()?);
    let dispatcher = Arc::new(AsyncDispatcher::new(32, move |request| {
        runtime.call(request)
    }));
    let dispatcher_for_ipc = Arc::clone(&dispatcher);
    let proxy_for_ipc = proxy.clone();

    let webview = WebViewBuilder::new()
        .with_custom_protocol("kourosh".to_owned(), |_webview_id, request| {
            let (body, content_type): (&[u8], &str) = match request.uri().path() {
                "/" | "/index.html" => (
                    include_bytes!("../../../examples/hello-vanilla/index.html"),
                    "text/html; charset=utf-8",
                ),
                "/bridge.js" => (
                    include_bytes!("../../../examples/hello-vanilla/bridge.js"),
                    "text/javascript; charset=utf-8",
                ),
                "/app.js" => (
                    include_bytes!("../../../examples/hello-vanilla/app.js"),
                    "text/javascript; charset=utf-8",
                ),
                "/style.css" => (
                    include_bytes!("../../../examples/hello-vanilla/style.css"),
                    "text/css; charset=utf-8",
                ),
                _ => (&[] as &[u8], "text/plain; charset=utf-8"),
            };
            Response::builder()
                .header(CONTENT_TYPE, content_type)
                .status(if body.is_empty() { 404 } else { 200 })
                .body(Cow::Owned(body.to_vec()))
                .expect("static protocol response is valid")
        })
        .with_https_scheme(true)
        .with_url("https://kourosh.app/index.html")
        // The initial document is packaged HTML. Any attempt to navigate away
        // is rejected before it can gain access to the IPC callback.
        .with_navigation_handler(|url| {
            url == TRUSTED_ORIGIN || url.starts_with("https://kourosh.app/")
        })
        .with_ipc_handler(move |request| {
            let uri = request.uri().to_string();
            let origin = if uri == TRUSTED_ORIGIN || uri.starts_with("https://kourosh.app/") {
                TRUSTED_ORIGIN
            } else {
                "untrusted"
            };
            let result = dispatcher_for_ipc.submit(request.body(), origin, Duration::from_secs(5));
            match result {
                Ok(receiver) => {
                    let response_proxy = proxy_for_ipc.clone();
                    thread::spawn(move || {
                        if let Ok(response) = receiver.recv() {
                            let _ = response_proxy.send_event(UserEvent::Response(response));
                        }
                    });
                }
                Err(error) => {
                    let _ = proxy_for_ipc
                        .send_event(UserEvent::Response(RpcResponse::failure(None, error)));
                }
            }
        })
        .build(&window)?;

    event_loop.run(move |event, _, control_flow| {
        *control_flow = ControlFlow::Wait;
        match event {
            Event::UserEvent(UserEvent::Response(response)) => {
                let payload = serde_json::to_string(&response).unwrap_or_else(|_| {
                    serde_json::to_string(&RpcResponse::failure(
                        response.id.clone(),
                        BridgeError {
                            code: "serialization_error".to_owned(),
                            message: "unable to serialize bridge response".to_owned(),
                        },
                    ))
                    .expect("fallback response is serializable")
                });
                let script = format!("window.__kouroshReceive({payload});");
                let _ = webview.evaluate_script(&script);
            }
            Event::WindowEvent {
                event: WindowEvent::CloseRequested,
                ..
            } => *control_flow = ControlFlow::Exit,
            _ => {}
        }
    });
}
