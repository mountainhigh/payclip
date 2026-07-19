"""简化验证：登录 → 测试关键页面跳转 → 截图菜单"""
import sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5173"


def check_page(page, path, expected_btn_text, page_name):
    """访问页面并验证关键按钮存在"""
    page.goto(BASE + path, wait_until="networkidle")
    page.wait_for_timeout(800)
    url = page.url
    btn = page.query_selector(f'button:has-text("{expected_btn_text}")')
    ok = btn is not None
    status = "OK" if ok else "FAIL"
    print(f"[{status}] {page_name}: url={url}, 找到「{expected_btn_text}」按钮={ok}")
    return ok


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        # 1. 登录
        page.goto(BASE + "/login", wait_until="networkidle")
        page.fill('input[type="text"]', "demo_admin")
        page.fill('input[type="password"]', "123456")
        page.click('button:has-text("登录")')
        page.wait_for_url("**/dashboard", timeout=10000)
        print("[OK] 登录成功\n")

        # 2. 统计菜单结构
        page.wait_for_timeout(500)
        # 只取一级菜单（sidebar-menu 的直接子元素）
        top_level = page.evaluate('''() => {
            const menu = document.querySelector('.sidebar-menu');
            if (!menu) return [];
            return Array.from(menu.children).map(el => {
                const isSub = el.classList.contains('el-sub-menu');
                const titleEl = isSub ? el.querySelector('.el-sub-menu__title') : el;
                const title = titleEl ? titleEl.innerText.trim() : '';
                let children = [];
                if (isSub) {
                    children = Array.from(el.querySelectorAll('.el-menu-item')).map(c => c.innerText.trim());
                }
                return { type: isSub ? 'group' : 'single', title, children };
            });
        }''')
        print(f"=== 一级菜单数量: {len(top_level)} ===")
        for i, m in enumerate(top_level):
            if m['type'] == 'single':
                print(f"  [{i + 1}] {m['title']}")
            else:
                print(f"  [{i + 1}] {m['title']} (分组, {len(m['children'])} 个子菜单)")
                for c in m['children']:
                    print(f"      └─ {c}")

        # 3. 测试各页面跳转
        print("\n=== 测试页面跳转 ===")
        check_page(page, "/salary-settlement", "核对", "薪资结算")
        check_page(page, "/system/users", "新增用户", "用户管理")
        check_page(page, "/system/cost-presets", "新增预设", "成本预设")
        check_page(page, "/system/bonus-tiers", "新增阶梯", "阶梯奖金")

        # 4. 测试 /system 重定向
        print("\n=== 测试 /system 重定向 ===")
        page.goto(BASE + "/system", wait_until="networkidle")
        page.wait_for_timeout(1000)
        url = page.url
        if "/system/users" in url:
            print(f"[OK] /system 重定向到 {url}")
        else:
            print(f"[FAIL] /system 重定向到 {url}（期望 /system/users）")

        # 5. 测试点击菜单项（验证菜单可点击）
        print("\n=== 测试点击菜单项 ===")
        page.goto(BASE + "/dashboard", wait_until="networkidle")
        page.wait_for_timeout(500)
        # 展开「财务」分组
        finance_title = page.query_selector('.el-sub-menu__title:has-text("财务")')
        if finance_title:
            finance_title.click()
            page.wait_for_timeout(500)
            settlement = page.query_selector('.el-menu-item:has-text("薪资结算")')
            if settlement:
                settlement.click()
                page.wait_for_timeout(1500)
                url = page.url
                if "/salary-settlement" in url:
                    print(f"[OK] 点击「薪资结算」菜单项跳转到 {url}")
                else:
                    print(f"[FAIL] 点击后 URL: {url}")
            else:
                print("[FAIL] 未找到「薪资结算」菜单项")
        else:
            print("[FAIL] 未找到「财务」分组")

        # 6. 截图菜单结构
        print("\n=== 截图菜单 ===")
        page.goto(BASE + "/dashboard", wait_until="networkidle")
        page.wait_for_timeout(500)
        # 展开所有分组
        for title_text in ['客户业务', '财务', '系统设置']:
            t = page.query_selector(f'.el-sub-menu__title:has-text("{title_text}")')
            if t:
                try:
                    t.click()
                    page.wait_for_timeout(300)
                except Exception:
                    pass
        page.screenshot(path="e:/code/ai_code/payclip/menu_structure.png", full_page=False)
        print("[OK] 菜单截图已保存: menu_structure.png")

        browser.close()
        print("\n[DONE] 验证完成")


if __name__ == "__main__":
    main()
