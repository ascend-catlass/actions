/**
 * 模板片段。
 *
 * 每个函数返回 HTML 字符串，供 index.html 渲染逻辑调用。
 * 视觉规范来自 smartisan-ui skill：灰阶文字、低饱和强调色、
 * 0.8px 描边、极淡投影、无纯黑。
 */
(function (global) {
  'use strict';

  /** 转义，防止记录内容里的 HTML 破坏结构。 */
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /** 结果标签：文案 + 配色。 */
  var OUTCOME = {
    dispatched: { label: '真实触发', cls: 'badge--dispatched' },
    dry_run:    { label: '测试',     cls: 'badge--dry_run' },
    denied:     { label: '名单拦截', cls: 'badge--denied' },
    ignored:    { label: '已忽略',   cls: 'badge--ignored' },
    rejected:   { label: '鉴权失败', cls: 'badge--rejected' },
    failed:     { label: '转发失败', cls: 'badge--failed' },
  };

  /** 概览格子（6 格横排）。 */
  function statCell(label, value, tone) {
    return '<div>' +
             '<span class="stat-num ' + (tone || '') + '">' + esc(value) + '</span>' +
             '<span class="stat-label">' + esc(label) + '</span>' +
           '</div>';
  }

  function statsGrid(counts) {
    var c = counts || {};
    return [
      statCell('真实触发',     c.dispatched || 0, 'n-ok'),
      statCell('测试(未触发)', c.dry_run    || 0, 'n-info'),
      statCell('名单拦截',     c.denied     || 0, 'n-warn'),
      statCell('已忽略',       c.ignored    || 0, 'n-mut'),
      statCell('转发失败',     c.failed     || 0, 'n-err'),
      statCell('鉴权失败',     c.rejected   || 0, 'n-err'),
    ].join('');
  }

  /** 事件分类标签：大类/小类，做成胶囊便于扫读。 */
  function categoryCell(e) {
    if (!e.category) return '<span class="dim">—</span>';

    var major = esc(e.category);
    // 大类决定配色，同一类的事件视觉成组
    var tone = ({ pr: 'pr', issue: 'issue', push: 'push' })[e.category] || 'other';

    if (!e.subtype) {
      return '<span class="cat cat--' + tone + '">' +
               '<span class="cat__major">' + major + '</span>' +
             '</span>';
    }
    // 大类与小类同在一个标签内，用分隔符与字重区分层次
    return '<span class="cat cat--' + tone + '">' +
             '<span class="cat__major">' + major + '</span>' +
             '<span class="cat__sep">/</span>' +
             '<span class="cat__sub">' + esc(e.subtype) + '</span>' +
           '</span>';
  }

  /** 来源单元格：有链接就做成可点击。 */
  function sourceCell(e) {
    var repo = e.repo || '';
    var short = repo ? repo.split('/').pop() : '';
    var iid = (e.iid !== null && e.iid !== undefined && e.iid !== '') ? ('#' + e.iid) : '';
    var text = esc(short) + (iid ? ' ' + esc(iid) : '');
    if (!repo && !iid) return '<span class="dim">—</span>';
    if (e.source_url) {
      return '<a class="link" href="' + esc(e.source_url) + '" target="_blank" rel="noopener">'
             + text + '</a>';
    }
    return '<span class="mono">' + text + '</span>';
  }

  /** 目标单元格：workflow + 运行链接（有 run id 就链到具体运行）。 */
  function targetCell(e) {
    if (!e.workflow) return '<span class="dim">—</span>';
    var name = '<span class="mono dim">' + esc(e.workflow) + '</span>';
    var link = '';
    if (e.run_url) {
      var label = e.run_id ? ('运行 #' + esc(e.run_id)) : '查看运行';
      link = '<a class="link link--run" href="' + esc(e.run_url) +
             '" target="_blank" rel="noopener">' + label + ' ↗</a>';
    } else if (e.outcome === 'dispatched') {
      link = '<span class="dim" style="font-size:11px">运行链接获取中</span>';
    } else if (e.outcome === 'dry_run') {
      link = '<span class="dim" style="font-size:11px">测试未触发</span>';
    }
    var detail = e.detail ? '<span class="detail">' + esc(e.detail) + '</span>' : '';
    return name + link + detail;
  }

  /** 一条记录渲染成表格行。 */
  function eventRow(e) {
    var o = OUTCOME[e.outcome] || { label: e.outcome || '-', cls: '' };
    var time = new Date(e.ts).toLocaleString('zh-CN', { hour12: false });
    var who = e.user || '—';
    var reason = e.reason ? esc(e.reason) : '—';

    // data-label 供移动端卡片式布局显示字段名
    return '<tr>' +
             '<td class="mono dim" data-label="时间">' +
               '<span class="badge ' + o.cls + ' badge--inline">' + esc(o.label) + '</span>' +
               '<span>' + esc(time) + '</span></td>' +
             '<td class="col-result" data-label="结果"><span class="badge ' + o.cls + '">' +
               esc(o.label) + '</span></td>' +
             '<td data-label="事件类型">' + categoryCell(e) + '</td>' +
             '<td class="mono" data-label="触发者">' + esc(who) + '</td>' +
             '<td data-label="来源">' + sourceCell(e) + '</td>' +
             '<td class="dim" data-label="原因">' + reason + '</td>' +
             '<td data-label="目标">' + targetCell(e) + '</td>' +
           '</tr>';
  }

  /** 记录表格。 */
  function eventTable(events, days) {
    if (!events || !events.length) {
      return '<div class="empty">最近 ' + esc(days) + ' 天没有请求</div>';
    }
    var head = '<table class="ev"><thead><tr>' +
      '<th>时间</th>' +
      '<th>结果</th>' +
      '<th>事件类型</th>' +
      '<th>触发者</th>' +
      '<th>来源</th>' +
      '<th>原因</th>' +
      '<th>目标 / 运行</th>' +
      '</tr></thead><tbody>';
    return head + events.map(eventRow).join('') + '</tbody></table>';
  }

  /** 名单来源摘要。 */
  function rosterSummary(status) {
    var counts = status.counts || {};
    var parts = Object.keys(counts).map(function (repo) {
      var roles = counts[repo] || {};
      var inner = Object.keys(roles).map(function (k) { return k + ' ' + roles[k]; }).join('、');
      return repo + '（' + inner + '）';
    });
    return parts.length ? parts.join('；') : '尚未加载';
  }

  global.STemplate = {
    esc: esc,
    OUTCOME: OUTCOME,
    statsGrid: statsGrid,
    eventTable: eventTable,
    categoryCell: categoryCell,
    rosterSummary: rosterSummary,
  };
})(window);
