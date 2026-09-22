import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./index.css";

const container = document.getElementById("root");
if (!container) {
  throw new Error("找不到 #root 挂载点，请检查 index.html");
}

// BrowserRouter 必须包在最外层：App 里的 <Routes> 依赖它提供的路由上下文。
// 放在 main.tsx 而不是 App.tsx，是为了让 App 保持"只是个组件"，
// 以后写测试时可以单独渲染 App 并套一个 MemoryRouter。
createRoot(container).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
