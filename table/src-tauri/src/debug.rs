// 功能：开发模式通过 WebView2 原生 CapturePreview 返回当前 WebView PNG。
// Created on 2026-11-01; Updated on 2026-11-01
// @author: https://github.com/Linmoqian

#[tauri::command]
pub async fn debug_webview_screenshot(window: tauri::WebviewWindow) -> Result<String, String> {
    #[cfg(all(windows, debug_assertions))]
    {
        use base64::{engine::general_purpose::STANDARD, Engine};
        use std::{sync::mpsc, time::Duration};
        use webview2_com::{
            CapturePreviewCompletedHandler,
            Microsoft::Web::WebView2::Win32::COREWEBVIEW2_CAPTURE_PREVIEW_IMAGE_FORMAT_PNG,
        };
        use windows::Win32::{
            Foundation::HGLOBAL,
            System::Com::{
                StructuredStorage::CreateStreamOnHGlobal, STATFLAG_NONAME, STATSTG, STREAM_SEEK_SET,
            },
        };

        if !window.is_visible().map_err(|e| e.to_string())?
            || window.is_minimized().map_err(|e| e.to_string())? {
            return Err("截图需要窗口可见且未最小化".into());
        }
        let (sender, receiver) = mpsc::channel::<Result<String, String>>();
        window.with_webview(move |webview| {
            let failure = sender.clone();
            // COM 对象只在 WebView UI 线程创建和使用，跨线程仅发送 PNG 字符串。
            let start = (|| -> windows::core::Result<()> {
                let stream = unsafe { CreateStreamOnHGlobal(HGLOBAL::default(), true)? };
                let captured = stream.clone();
                let callback = CapturePreviewCompletedHandler::create(Box::new(move |status| {
                    let result = (|| -> Result<String, String> {
                        status.map_err(|e| e.to_string())?;
                        let mut stat = STATSTG::default();
                        unsafe { captured.Stat(&mut stat, STATFLAG_NONAME) }.map_err(|e| e.to_string())?;
                        if stat.cbSize == 0 || stat.cbSize > 32 * 1024 * 1024 {
                            return Err("PNG 截图为空或超过 32 MiB".into());
                        }
                        unsafe { captured.Seek(0, STREAM_SEEK_SET, None) }.map_err(|e| e.to_string())?;
                        let mut bytes = vec![0u8; stat.cbSize as usize];
                        let mut read = 0u32;
                        unsafe { captured.Read(bytes.as_mut_ptr().cast(), bytes.len() as u32, Some(&mut read)) }
                            .ok().map_err(|e| e.to_string())?;
                        if read as usize != bytes.len() { return Err("PNG 截图读取不完整".into()); }
                        Ok(STANDARD.encode(bytes))
                    })();
                    let _ = sender.send(result);
                    Ok(())
                }));
                unsafe {
                    webview.controller().CoreWebView2()?.CapturePreview(
                        COREWEBVIEW2_CAPTURE_PREVIEW_IMAGE_FORMAT_PNG, &stream, &callback,
                    )?;
                }
                Ok(())
            })();
            if let Err(error) = start { let _ = failure.send(Err(error.to_string())); }
        }).map_err(|e| e.to_string())?;
        tauri::async_runtime::spawn_blocking(move || {
            receiver.recv_timeout(Duration::from_secs(5))
                .map_err(|_| "WebView 截图超时或窗口已关闭".to_string())?
        }).await.map_err(|e| e.to_string())?
    }
    #[cfg(not(all(windows, debug_assertions)))]
    {
        let _ = window;
        Err("截图调试接口仅支持 Windows 开发构建".into())
    }
}
