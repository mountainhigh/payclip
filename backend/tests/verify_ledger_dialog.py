"""快速验证内账结算核对弹窗：登录 → 打开系统设置 → 切到内账结算 tab → 点击核对 → 截图"""
import sys
import time
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5173"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        # 1. 登录
        page.goto(BASE + "/login", wait_until="networkidle")
        page.fill('input[placeholder*="用户名"], input[type="text"]', "demo_admin")
        page.fill('input[type="password"]', "123456")
        page.click('button:has-text("登录")')
        page.wait_for_url("**/dashboard", timeout=10000)
        print("[OK] 登录成功")

        # 2. 打开系统设置
        page.goto(BASE + "/system", wait_until="networkidle")
        page.wait_for_timeout(800)

        # 3. 点击「内账结算」tab
        tab_found = False
        for selector in [
            '.el-tabs__item:has-text("内账结算")',
            'div.el-tabs__item:has-text("内账结算")',
            'text="内账结算"',
        ]:
            try:
                page.click(selector, timeout=3000)
                tab_found = True
                print(f"[OK] 使用选择器 {selector} 切换到内账结算 tab")
                break
            except Exception as e:
                print(f"[SKIP] 选择器 {selector} 失败: {e}")
        if not tab_found:
            # 兜底：遍历所有 tab 项文字
            tabs = page.query_selector_all('.el-tabs__item')
            print(f"[INFO] 找到 {len(tabs)} 个 tab 项")
            for t in tabs:
                txt = t.inner_text()
                print(f"  - tab: {txt!r}")
                if "内账" in txt or "结算" in txt:
                    t.click()
                    tab_found = True
                    print(f"[OK] 点击 tab: {txt!r}")
                    break
        if not tab_found:
            print("[FAIL] 未找到内账结算 tab")
            page.screenshot(path="e:/code/ai_code/payclip/system_page.png")
            browser.close()
            sys.exit(1)

        page.wait_for_timeout(800)

        # 4. 截图保存 tab 内容
        page.screenshot(path="e:/code/ai_code/payclip/ledger_tab.png", full_page=True)
        print("[OK] 截图 ledger_tab.png")

        # 5. 设置年份 2026、月份 7（如果当前不是的话）
        # 找到两个 input-number
        nums = page.query_selector_all('.el-input-number')
        print(f"[INFO] 找到 {len(nums)} 个 input-number")
        if len(nums) >= 2:
            year_input = nums[0].query_selector('input')
            month_input = nums[1].query_selector('input')
            year_input.fill("2026")
            month_input.fill("7")
            page.wait_for_timeout(300)

        # 6. 点击「核对」按钮
        verify_btn = None
        for sel in ['button:has-text("核对")', '.el-button--primary:has-text("核对")']:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    verify_btn = btn
                    print(f"[OK] 找到核对按钮: {sel}")
                    break
            except Exception:
                pass
        if not verify_btn:
            print("[FAIL] 未找到核对按钮")
            page.screenshot(path="e:/code/ai_code/payclip/no_verify_btn.png", full_page=True)
            browser.close()
            sys.exit(1)
        verify_btn.click()
        page.wait_for_timeout(1500)

        # 7. 截图弹窗
        page.screenshot(path="e:/code/ai_code/payclip/verify_dialog.png", full_page=True)
        print("[OK] 截图 verify_dialog.png")

        # 8. 验证弹窗内容
        dialog = page.query_selector('.el-dialog:visible, .el-dialog__wrapper:visible, .el-overlay-dialog .el-dialog')
        if not dialog:
            # 尝试另一种选择器
            dialog = page.query_selector('.el-dialog')
        if dialog:
            title = dialog.query_selector('.el-dialog__title')
            title_text = title.inner_text() if title else "(无标题)"
            print(f"[OK] 弹窗标题: {title_text!r}")

            # 检查统计卡片
            cards = dialog.query_selector_all('.stat-card')
            print(f"[OK] 找到 {len(cards)} 个统计卡片")
            for i, c in enumerate(cards):
                label = c.query_selector('.stat-label')
                value = c.query_selector('.stat-value')
                if label and value:
                    print(f"  - 卡片 {i + 1}: {label.inner_text()} = {value.inner_text()}")

            # 检查表格行数
            rows = dialog.query_selector_all('.el-table__row')
            print(f"[OK] 收款明细表格行数: {len(rows)}")

            # 检查底部按钮
            footer_btns = dialog.query_selector_all('button')
            print(f"[OK] 弹窗内按钮数量: {len(footer_btns)}")
            for b in footer_btns:
                txt = b.inner_text().strip()
                disabled = b.get_attribute('disabled')
                cls = b.get_attribute('class') or ''
                print(f"  - 按钮: {txt!r}, disabled={disabled}, class包含disabled={'is-disabled' in cls}")
        else:
            print("[FAIL] 未找到弹窗")

        # 9. 测试导出按钮 - 不真的下载，只点击看响应
        # 关闭弹窗
        close_btn = page.query_selector('.el-dialog button:has-text("关闭")')
        if close_btn:
            close_btn.click()
            page.wait_for_timeout(500)

        browser.close()
        print("\n[DONE] 验证完成")


if __name__ == "__main__":
    main()
