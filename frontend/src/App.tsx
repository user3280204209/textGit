/**
 * 应用外壳：导航 + 路由。
 *
 * 为什么现在就引入路由，而不是在 App 里用 if/else 切页面？
 * 因为项目注定要有多个页面（对话 / 资源 / 学习路径），
 * 用 if/else 拼出来的"假路由"迟早要重写，不如一开始就用标准做法。
 *
 * 新增一个页面只需要两步：
 *   1. pages/ 下建组件；
 *   2. 下面 <Routes> 里加一行 <Route>，导航里加一个 <NavLink>。
 */

import { NavLink, Route, Routes } from "react-router-dom";

import ChatPage from "@/pages/ChatPage";
import DebugPage from "@/pages/DebugPage";

/** NavLink 的 className 可以是函数，参数里带 isActive —— 用它做高亮 */
function navClass({ isActive }: { isActive: boolean }): string {
  return isActive ? "nav__link nav__link--active" : "nav__link";
}

export default function App() {
  return (
    <div className="shell">
      <nav className="nav">
        {/* end 表示"仅当路径完全等于 / 时才高亮"，否则 /debug 也会点亮"对话" */}
        <NavLink to="/" end className={navClass}>
          对话
        </NavLink>
        <NavLink to="/debug" className={navClass}>
          环境自检
        </NavLink>
      </nav>

      <main className="shell__main">
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/debug" element={<DebugPage />} />
        </Routes>
      </main>
    </div>
  );
}
