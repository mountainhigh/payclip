"""验证：1.成本预设已移到客户业务组 2.菜单图标颜色可见 3.各状态样式正确"""
import sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5173"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # 有头模式便于观察
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        # 1. 登录
        page.goto(BASE + "/login", wait_until="networkidle")
        page.fill('input[type="text"]', "demo_admin")
        page.fill('input[type="password"]', "123456")
        page.click('button:has-text("登录")')
        page.wait_for_url("**/dashboard", timeout=10000)
        page.wait_for_timeout(800)
        print("[OK] 登录成功\n")

        # 2. 收集菜单结构
        menu_info = page.evaluate('''() => {
            const menu = document.querySelector('.sidebar-menu');
            if (!menu) return [];
            const result = [];
            for (const el of menu.children) {
                const isSub = el.classList.contains('el-sub-menu');
                const titleEl = isSub ? el.querySelector('.el-sub-menu__title') : el;
                const title = titleEl ? titleEl.innerText.trim() : '';
                let children = [];
                if (isSub) {
                    children = Array.from(el.querySelectorAll('.el-menu-item'))
                        .map(c => c.innerText.trim());
                }
                result.push({ type: isSub ? 'group' : 'single', title, children });
            }
            return result;
        }''')
        print("=== 菜单结构 ===")
        for m in menu_info:
            if m['type'] == 'single':
                print(f"  {m['title']}")
            else:
                print(f"  {m['title']} (分组)")
                for c in m['children']:
                    print(f"      └─ {c}")

        # 3. 验证成本预设位置
        business_group = next((m for m in menu_info if m['title'] == '客户业务'), None)
        system_group = next((m for m in menu_info if m['title'] == '系统设置'), None)
        print("\n=== 验证成本预设位置 ===")
        if business_group and '成本预设' in business_group['children']:
            idx = business_group['children'].index('成本预设')
            print(f"[OK] 成本预设在「客户业务」组中，位置 {idx + 1}（共 {len(business_group['children'])} 项）")
            print(f"  顺序: {' → '.join(business_group['children'])}")
        else:
            print("[FAIL] 成本预设不在「客户业务」组中")
        if system_group and '成本预设' not in system_group['children']:
            print(f"[OK] 「系统设置」组中已无成本预设，剩余: {system_group['children']}")
        else:
            print(f"[FAIL] 「系统设置」组仍有成本预设: {system_group['children'] if system_group else '无系统设置组'}")

        # 4. 验证图标可见性 - 检查 svg 的计算颜色
        print("\n=== 验证图标可见性 ===")
        # 展开「客户业务」和「系统设置」分组
        for title_text in ['客户业务', '系统设置']:
            t = page.query_selector(f'.el-sub-menu__title:has-text("{title_text}")')
            if t:
                t.click()
                page.wait_for_timeout(400)

        # 检查各状态下的图标颜色
        icon_colors = page.evaluate('''() => {
            const result = [];
            // 1. 分组标题图标
            const subTitles = document.querySelectorAll('.sidebar-menu .el-sub-menu__title .el-icon');
            subTitles.forEach((el, i) => {
                const style = window.getComputedStyle(el);
                const color = style.color;
                const titleEl = el.closest('.el-sub-menu__title');
                const title = titleEl ? titleEl.innerText.trim() : '(未知)';
                result.push({ location: `分组标题: ${title}`, color });
            });
            // 2. 普通菜单项图标（取第一个非 active 的）
            const menuItems = document.querySelectorAll('.sidebar-menu .el-menu-item:not(.is-active) .el-icon');
            menuItems.forEach((el, i) => {
                if (i < 3) {
                    const style = window.getComputedStyle(el);
                    const itemEl = el.closest('.el-menu-item');
                    const title = itemEl ? itemEl.innerText.trim() : '(未知)';
                    result.push({ location: `菜单项: ${title}`, color: style.color });
                }
            });
            // 3. active 菜单项图标
            const activeItem = document.querySelector('.sidebar-menu .el-menu-item.is-active .el-icon');
            if (activeItem) {
                const style = window.getComputedStyle(activeItem);
                const itemEl = activeItem.closest('.el-menu-item');
                const title = itemEl ? itemEl.innerText.trim() : '(未知)';
                result.push({ location: `激活项: ${title}`, color: style.color });
            }
            return result;
        }''')
        for item in icon_colors:
            print(f"  {item['location']}: color={item['color']}")

        # 5. hover 测试 - 跳过（折叠菜单项不可见会超时），改为通过 CSS 变量验证
        print("\n=== hover 颜色（CSS 变量）===")
        hover_vars = page.evaluate('''() => {
            const menu = document.querySelector('.sidebar-menu');
            const style = window.getComputedStyle(menu);
            return {
                hoverText: style.getPropertyValue('--el-menu-hover-text-color').trim(),
                hoverBg: style.getPropertyValue('--el-menu-hover-bg-color').trim(),
                activeColor: style.getPropertyValue('--el-menu-active-color').trim(),
                textColor: style.getPropertyValue('--el-menu-text-color').trim()
            };
        }''')
        for k, v in hover_vars.items():
            print(f"  {k}: {v!r}")

        # 6. 测试成本预设页面（直接 URL 访问，因为分组可能折叠）
        print("\n=== 测试成本预设页面 ===")
        page.goto(BASE + "/system/cost-presets", wait_until="networkidle")
        page.wait_for_timeout(1000)
        url = page.url
        add_btn = page.query_selector('button:has-text("新增预设")')
        if '/system/cost-presets' in url and add_btn:
            print(f"[OK] 成本预设页面正常加载: {url}（找到「新增预设」按钮）")
        else:
            print(f"[FAIL] url={url}, 找到按钮={add_btn is not None}")

        # 7. 截图保存（展开客户业务和系统设置分组）
        page.goto(BASE + "/dashboard", wait_until="networkidle")
        page.wait_for_timeout(500)
        for title_text in ['客户业务', '财务', '系统设置']:
            t = page.query_selector(f'.el-sub-menu__title:has-text("{title_text}")')
            if t:
                try:
                    t.click()
                    page.wait_for_timeout(300)
                except Exception:
                    pass
        page.screenshot(path="e:/code/ai_code/payclip/menu_fixed.png", full_page=False)
        print("\n[OK] 截图保存: menu_fixed.png")

        browser.close()
        print("\n[DONE] 验证完成")


if __name__ == "__main__":
    main()
