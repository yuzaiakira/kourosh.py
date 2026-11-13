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
struct HostOptions {
    app: Option<std::path::PathBuf>,
    frontend: Option<std::path::PathBuf>,
    packaged_root: Option<std::path::PathBuf>,
    dev_url: Option<String>,
    trusted_origin: String,
    identifier: String,
    title: String,
    width: u32,
    height: u32,
}

#[cfg(windows)]
fn run_windows_host() -> Result<(), Box<dyn std::error::Error>> {
    use kourosh_bridge::{response_for_error, AsyncDispatcher, BridgeError, RpcResponse};
    use kourosh_python::{PythonRuntime, RuntimeAdapter};
    use std::path::Path;
    use std::sync::Arc;
    use std::thread;
    use std::time::Duration;
    use tao::dpi::LogicalSize;
    use tao::event::{Event, WindowEvent};
    use tao::event_loop::{ControlFlow, EventLoopBuilder};
    use tao::window::WindowBuilder;
    use wry::{WebContext, WebViewBuilder, WebViewBuilderExtWindows};

    enum UserEvent {
        Response(RpcResponse),
    }

    let options = parse_host_options()?;
    if options.app.is_some() {
        std::env::set_var("KOUROSH_HOST_APP", "1");
    }
    if let Some(root) = options.packaged_root.as_deref() {
        let python_root = root.join("python");
        let app_root = root.join("app");
        let runtime_python = root.join("runtime").join("python");
        std::env::set_var("KOUROSH_PACKAGED_ROOT", root);
        std::env::set_var("PYTHONHOME", &python_root);
        std::env::set_var("PYTHONNOUSERSITE", "1");
        std::env::remove_var("PYTHONPATH");
        let search_path = std::env::join_paths([app_root, runtime_python])?;
        std::env::set_var("KOUROSH_PYTHON_PATH", search_path);
    }
    let webview_data_directory = webview_user_data_directory(&options.identifier)?;
    let mut web_context = WebContext::new(Some(webview_data_directory));
    let event_loop = EventLoopBuilder::<UserEvent>::with_user_event().build();
    let proxy = event_loop.create_proxy();
    let window = WindowBuilder::new()
        .with_title(&options.title)
        .with_inner_size(LogicalSize::new(options.width, options.height))
        .build(&event_loop)?;
    let runtime: Arc<dyn RuntimeAdapter> = Arc::new(match options.app.as_deref() {
        Some(path) => PythonRuntime::new_with_app(path)?,
        None => PythonRuntime::new()?,
    });
    let allowed_methods = runtime.methods().to_vec();
    let runtime_for_dispatch = Arc::clone(&runtime);
    let dispatcher = Arc::new(AsyncDispatcher::new_with_methods_cancellable(
        32,
        allowed_methods,
        move |request, cancellation| {
            runtime_for_dispatch.dispatch_with_cancellation(request, &cancellation)
        },
    ));
    let dispatcher_for_ipc = Arc::clone(&dispatcher);
    let dispatcher_for_lifecycle = Arc::clone(&dispatcher);
    let runtime_for_lifecycle = Arc::clone(&runtime);
    let proxy_for_ipc = proxy.clone();
    let trusted_origin = options.trusted_origin.clone();

    let static_root = match options.frontend.as_deref() {
        Some(frontend) => frontend
            .parent()
            .ok_or("frontend path has no parent")?
            .canonicalize()?,
        None => Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../examples/hello-vanilla")
            .canonicalize()?,
    };
    let initial_url = options
        .dev_url
        .clone()
        .unwrap_or_else(|| "https://kourosh.app/index.html".to_owned());
    let navigation_origin = trusted_origin.clone();
    let ipc_origin = trusted_origin.clone();
    let webview = WebViewBuilder::with_web_context(&mut web_context)
        .with_custom_protocol("kourosh".to_owned(), move |_webview_id, request| {
            custom_protocol_response(&static_root, request.uri().path())
        })
        .with_https_scheme(true)
        .with_url(&initial_url)
        // The initial document is packaged HTML. Any attempt to navigate away
        // is rejected before it can gain access to the IPC callback.
        .with_navigation_handler(move |url| {
            url == navigation_origin || url.starts_with(&format!("{navigation_origin}/"))
        })
        .with_ipc_handler(move |request| {
            let uri = request.uri().to_string();
            let origin = if uri == ipc_origin || uri.starts_with(&format!("{ipc_origin}/")) {
                ipc_origin.as_str()
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
                    let _ = proxy_for_ipc.send_event(UserEvent::Response(response_for_error(
                        request.body(),
                        error,
                    )));
                }
            }
        })
        .build(&window)?;

    event_loop.run(move |event, _, control_flow| {
        // Keep the context alive for the lifetime of the WebView. Its
        // directory is under LOCALAPPDATA, never beside a read-only install.
        let _web_context_guard = &web_context;
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
            } => {
                let _ = webview.evaluate_script(
                    "window.__kouroshRejectAll && window.__kouroshRejectAll({code:'window_closed',message:'window is closing'});",
                );
                dispatcher_for_lifecycle.shutdown();
                runtime_for_lifecycle.shutdown();
                *control_flow = ControlFlow::Exit;
            }
            _ => {}
        }
    });
}

#[cfg(windows)]
fn custom_protocol_response(
    root: &std::path::Path,
    request_path: &str,
) -> wry::http::Response<std::borrow::Cow<'static, [u8]>> {
    use std::borrow::Cow;
    use std::fs;
    use wry::http::{header::CONTENT_TYPE, Response};
    let relative = request_path.trim_start_matches('/');
    let relative = if relative.is_empty() {
        "index.html"
    } else {
        relative
    };
    let rejected = relative.contains("..")
        || relative.contains('\\')
        || relative.contains('\0')
        || relative.contains('%')
        || relative.starts_with('/');
    let path = root.join(relative);
    let valid_path = !rejected
        && path
            .canonicalize()
            .map(|canonical| canonical.starts_with(root))
            .unwrap_or(false);
    let body = if valid_path {
        fs::read(&path).unwrap_or_default()
    } else {
        Vec::new()
    };
    let content_type = match std::path::Path::new(relative)
        .extension()
        .and_then(|extension| extension.to_str())
    {
        Some("html") => "text/html; charset=utf-8",
        Some("js") => "text/javascript; charset=utf-8",
        Some("css") => "text/css; charset=utf-8",
        Some("json") => "application/json; charset=utf-8",
        _ => "application/octet-stream",
    };
    Response::builder()
        .header(CONTENT_TYPE, content_type)
        .status(if body.is_empty() { 404 } else { 200 })
        .body(Cow::Owned(body))
        .expect("static protocol response is valid")
}

#[cfg(windows)]
fn parse_host_options() -> Result<HostOptions, Box<dyn std::error::Error>> {
    use std::env;
    use std::path::PathBuf;

    let mut app = None;
    let mut frontend = None;
    let mut dev_url = None;
    let mut trusted_origin = kourosh_bridge::TRUSTED_ORIGIN.to_owned();
    let mut identifier = "kourosh-dev".to_owned();
    let mut title = "Kourosh.py".to_owned();
    let mut width = 960;
    let mut height = 640;
    let mut args = env::args_os().skip(1);
    while let Some(argument) = args.next() {
        let argument = argument.to_string_lossy();
        match argument.as_ref() {
            "--app" => {
                app = Some(PathBuf::from(next_argument("--app", &mut args)?).canonicalize()?)
            }
            "--frontend" => {
                frontend = Some(
                    PathBuf::from(next_argument("--frontend", &mut args)?.as_str())
                        .canonicalize()?,
                )
            }
            "--dev-url" => {
                let value = next_argument("--dev-url", &mut args)?;
                let origin = validate_dev_url(&value)?;
                dev_url = Some(value);
                trusted_origin = origin;
            }
            "--identifier" => identifier = next_argument("--identifier", &mut args)?,
            "--title" => title = next_argument("--title", &mut args)?,
            "--width" => width = next_argument("--width", &mut args)?.parse()?,
            "--height" => height = next_argument("--height", &mut args)?.parse()?,
            unknown => return Err(format!("unknown host argument: {unknown}").into()),
        }
    }
    let packaged_root = if app.is_none() && frontend.is_none() && dev_url.is_none() {
        discover_packaged_paths()?.map(|packaged| {
            app = Some(packaged.app);
            frontend = Some(packaged.frontend);
            if let Some(packaged_title) = packaged.title {
                title = packaged_title;
            }
            if let Some(packaged_width) = packaged.width {
                width = packaged_width;
            }
            if let Some(packaged_height) = packaged.height {
                height = packaged_height;
            }
            identifier = packaged.identifier;
            packaged.root
        })
    } else {
        None
    };
    if title.is_empty() || width == 0 || height == 0 || width > 16_384 || height > 16_384 {
        return Err("invalid window configuration".into());
    }
    if !valid_identifier(&identifier) {
        return Err("invalid application identifier".into());
    }
    if identifier == "kourosh-dev" {
        if let Some(app) = &app {
            identifier = development_identifier(app);
        }
    }
    if packaged_root.is_none() {
        if let (Some(app), Some(frontend)) = (&app, &frontend) {
            let root = app.parent().ok_or("app path has no parent")?;
            if !frontend.starts_with(root) {
                return Err("frontend must be inside the application directory".into());
            }
        }
    }
    Ok(HostOptions {
        app,
        frontend,
        packaged_root,
        dev_url,
        trusted_origin,
        identifier,
        title,
        width,
        height,
    })
}

#[cfg(windows)]
#[derive(serde::Deserialize)]
struct PackageManifest {
    app: String,
    frontend: String,
    python: String,
    runtime_python: String,
    identifier: String,
    title: Option<String>,
    width: Option<u32>,
    height: Option<u32>,
}

#[cfg(windows)]
struct PackagedPaths {
    root: std::path::PathBuf,
    app: std::path::PathBuf,
    frontend: std::path::PathBuf,
    title: Option<String>,
    width: Option<u32>,
    height: Option<u32>,
    identifier: String,
}

#[cfg(windows)]
fn discover_packaged_paths() -> Result<Option<PackagedPaths>, Box<dyn std::error::Error>> {
    use std::fs;

    let executable = std::env::current_exe()?;
    let Some(root) = executable.parent() else {
        return Ok(None);
    };
    let manifest_path = root.join("runtime").join("manifest.json");
    if !manifest_path.is_file() {
        return Ok(None);
    }
    let manifest: PackageManifest = serde_json::from_slice(&fs::read(&manifest_path)?)
        .map_err(|error| format!("invalid packaged runtime manifest: {error}"))?;
    let app = packaged_path(root, &manifest.app, "application entrypoint")?;
    let frontend = packaged_path(root, &manifest.frontend, "frontend")?;
    let python = packaged_path(root, &manifest.python, "Python runtime")?;
    let runtime_python = packaged_path(root, &manifest.runtime_python, "Kourosh runtime")?;
    if !app.is_file() || !frontend.is_file() || !python.is_dir() || !runtime_python.is_dir() {
        return Err("packaged application is missing a required runtime resource".into());
    }
    Ok(Some(PackagedPaths {
        root: root.to_path_buf(),
        app,
        frontend,
        title: manifest.title,
        width: manifest.width,
        height: manifest.height,
        identifier: manifest.identifier,
    }))
}

#[cfg(windows)]
fn webview_user_data_directory(
    identifier: &str,
) -> Result<std::path::PathBuf, Box<dyn std::error::Error>> {
    use std::fs;
    use std::path::PathBuf;

    let base = std::env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .or_else(|| {
            std::env::var_os("USERPROFILE")
                .map(PathBuf::from)
                .map(|profile| profile.join("AppData").join("Local"))
        })
        .ok_or(
            "Windows LOCALAPPDATA/USERPROFILE is unavailable; cannot create WebView2 user data",
        )?;
    let vendor_root = base.join("Kourosh");
    if vendor_root.is_symlink() {
        return Err("WebView2 user-data root must not be a symlink".into());
    }
    fs::create_dir_all(&vendor_root)?;
    let application_root = vendor_root.join(identifier);
    if application_root.is_symlink() {
        return Err("WebView2 application data directory must not be a symlink".into());
    }
    fs::create_dir_all(&application_root)?;
    let canonical_base = base.canonicalize()?;
    let canonical_application = application_root.canonicalize()?;
    if !canonical_application.starts_with(&canonical_base) {
        return Err("WebView2 user-data directory escaped LOCALAPPDATA".into());
    }
    Ok(canonical_application)
}

#[cfg(windows)]
fn valid_identifier(value: &str) -> bool {
    let mut characters = value.chars();
    let Some(first) = characters.next() else {
        return false;
    };
    value.len() <= 128
        && (first == '_' || first.is_ascii_alphabetic())
        && characters.all(|character| {
            character == '_'
                || character == '-'
                || character == '.'
                || character.is_ascii_alphanumeric()
        })
}

#[cfg(windows)]
fn development_identifier(path: &std::path::Path) -> String {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};
    let mut hasher = DefaultHasher::new();
    path.to_string_lossy().hash(&mut hasher);
    format!("kourosh-dev-{:016x}", hasher.finish())
}

#[cfg(windows)]
fn packaged_path(
    root: &std::path::Path,
    relative: &str,
    label: &str,
) -> Result<std::path::PathBuf, Box<dyn std::error::Error>> {
    use std::path::PathBuf;
    let relative_path = PathBuf::from(relative);
    if relative_path.is_absolute()
        || relative_path
            .components()
            .any(|component| matches!(component, std::path::Component::ParentDir))
    {
        return Err(format!("packaged {label} path escapes the application directory").into());
    }
    let path = root.join(relative_path).canonicalize()?;
    if !path.starts_with(root) {
        return Err(format!("packaged {label} path escapes the application directory").into());
    }
    Ok(path)
}

#[cfg(windows)]
fn validate_dev_url(url: &str) -> Result<String, Box<dyn std::error::Error>> {
    let prefix = "http://127.0.0.1:";
    let port_start = url
        .strip_prefix(prefix)
        .ok_or("development URL must use http://127.0.0.1:<port>")?;
    let (port, path) = port_start.split_once('/').unwrap_or((port_start, ""));
    let port_number: u16 = port
        .parse()
        .map_err(|_| "development URL has an invalid port")?;
    if port_number == 0 || !path.is_empty() && path != "index.html" {
        return Err("development URL must contain only a loopback origin".into());
    }
    Ok(format!("{prefix}{port_number}"))
}

#[cfg(windows)]
fn next_argument<I: Iterator<Item = std::ffi::OsString>>(
    name: &str,
    args: &mut I,
) -> Result<String, Box<dyn std::error::Error>> {
    args.next()
        .map(|value| value.to_string_lossy().into_owned())
        .ok_or_else(|| format!("missing value for {name}").into())
}
