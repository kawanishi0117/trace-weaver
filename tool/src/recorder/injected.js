/**
 * injected.js — ページ注入スクリプト
 *
 * ブラウザページに注入され、ユーザー操作（click, input, keydown）を
 * 捕捉してセレクタ情報とともに Python 側に送信する。
 * Playwright codegen のような赤いハイライト枠は表示しない。
 */

(() => {
  // 二重注入防止
  if (window.__brt_recorder_injected) return;
  window.__brt_recorder_injected = true;

  /**
   * 要素から最適なセレクタ情報を抽出する。
   * 優先順位: data-testid > role+name > label > placeholder > text > css
   */
  function extractSelector(el) {
    const info = { tag: el.tagName.toLowerCase() };

    // data-testid
    const testId = el.getAttribute('data-testid');
    if (testId) {
      info.type = 'testId';
      info.value = testId;
      return info;
    }

    // ARIA role + accessible name
    const role = el.getAttribute('role') || getImplicitRole(el);
    if (role) {
      const name = getAccessibleName(el);
      info.type = 'role';
      info.role = role;
      if (name) info.name = name;
      return info;
    }

    // label (フォーム要素)
    if (el.labels && el.labels.length > 0) {
      const labelText = el.labels[0].textContent.trim();
      if (labelText) {
        info.type = 'label';
        info.value = labelText;
        return info;
      }
    }

    // placeholder
    const placeholder = el.getAttribute('placeholder');
    if (placeholder) {
      info.type = 'placeholder';
      info.value = placeholder;
      return info;
    }

    // テキスト内容（短いテキストのみ）
    const text = el.textContent.trim();
    if (text && text.length <= 80 && el.children.length === 0) {
      info.type = 'text';
      info.value = text;
      return info;
    }

    // CSS セレクタ（フォールバック）
    info.type = 'css';
    info.value = buildCssSelector(el);
    return info;
  }

  /** HTML 要素の暗黙的 ARIA ロールを返す */
  function getImplicitRole(el) {
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || '').toLowerCase();
    const roleMap = {
      'a': el.hasAttribute('href') ? 'link' : null,
      'button': 'button',
      'input': type === 'checkbox' ? 'checkbox'
             : type === 'radio' ? 'radio'
             : type === 'submit' ? 'button'
             : (type === 'text' || type === 'email' || type === 'password'
                || type === 'search' || type === 'tel' || type === 'url'
                || type === '' || type === 'number') ? 'textbox'
             : null,
      'select': 'combobox',
      'textarea': 'textbox',
      'h1': 'heading', 'h2': 'heading', 'h3': 'heading',
      'h4': 'heading', 'h5': 'heading', 'h6': 'heading',
      'img': 'img',
      'nav': 'navigation',
      'main': 'main',
    };
    return roleMap[tag] || null;
  }

  /** 要素のアクセシブルネームを取得する */
  function getAccessibleName(el) {
    // aria-label
    const ariaLabel = el.getAttribute('aria-label');
    if (ariaLabel) return ariaLabel;

    // aria-labelledby
    const labelledBy = el.getAttribute('aria-labelledby');
    if (labelledBy) {
      const labelEl = document.getElementById(labelledBy);
      if (labelEl) return labelEl.textContent.trim();
    }

    // title 属性
    const title = el.getAttribute('title');
    if (title) return title;

    // テキスト内容（短い場合のみ）
    const text = el.textContent.trim();
    if (text && text.length <= 80) return text;

    return null;
  }

  /** フォールバック用の CSS セレクタを構築する */
  function buildCssSelector(el) {
    // id があればそれを使う
    if (el.id) return `#${CSS.escape(el.id)}`;

    const tag = el.tagName.toLowerCase();
    const classes = Array.from(el.classList)
      .filter(c => !c.startsWith('__') && c.length < 40)
      .slice(0, 3);

    if (classes.length > 0) {
      return `${tag}.${classes.map(c => CSS.escape(c)).join('.')}`;
    }

    // nth-child フォールバック
    const parent = el.parentElement;
    if (parent) {
      const siblings = Array.from(parent.children).filter(
        s => s.tagName === el.tagName
      );
      if (siblings.length > 1) {
        const idx = siblings.indexOf(el) + 1;
        return `${tag}:nth-child(${idx})`;
      }
    }

    return tag;
  }

  // --- イベントリスナー ---

  // click イベント（キャプチャフェーズで捕捉）
  document.addEventListener('click', (e) => {
    const el = e.target;
    if (!el || el === document.body || el === document.documentElement) return;

    const selector = extractSelector(el);
    window.__brt_on_action(JSON.stringify({
      action: 'click',
      selector: selector,
      url: location.href,
      timestamp: Date.now(),
    }));
  }, true);

  // input イベント（fill 検出用、デバウンス付き）
  let inputTimer = null;
  let lastInputTarget = null;
  let lastInputValue = '';

  document.addEventListener('input', (e) => {
    const el = e.target;
    if (!el) return;

    lastInputTarget = el;
    lastInputValue = el.value || '';

    // 300ms デバウンス: 連続入力を1つの fill にまとめる
    clearTimeout(inputTimer);
    inputTimer = setTimeout(() => {
      if (!lastInputTarget) return;
      const selector = extractSelector(lastInputTarget);
      window.__brt_on_action(JSON.stringify({
        action: 'fill',
        selector: selector,
        value: lastInputValue,
        url: location.href,
        timestamp: Date.now(),
      }));
      lastInputTarget = null;
      lastInputValue = '';
    }, 300);
  }, true);

  // keydown イベント（Enter, Tab, Escape のみ記録）
  const RECORD_KEYS = new Set(['Enter', 'Tab', 'Escape']);
  document.addEventListener('keydown', (e) => {
    if (!RECORD_KEYS.has(e.key)) return;

    const el = e.target;
    const selector = el ? extractSelector(el) : { type: 'css', value: 'body' };
    window.__brt_on_action(JSON.stringify({
      action: 'press',
      selector: selector,
      key: e.key,
      url: location.href,
      timestamp: Date.now(),
    }));
  }, true);

})();
