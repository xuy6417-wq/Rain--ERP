'use client';

import { CSSProperties, FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';

const API = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');

type Supplier = { id: number; name: string };
type Warehouse = { id: number; code: string; name: string };
type SKU = { id: number; sku_code: string; barcode?: string };
type Product = { id: number; spu_code: string; name_cn: string; skus: SKU[] };
type POLine = { id: number; sku_id: number; sku_code: string; quantity: number; received_quantity: number; remaining_quantity: number; unit_price_rmb: string; line_total_rmb: string };
type PurchaseOrder = { id: number; po_number: string; supplier_name: string; warehouse_name: string; status: string; note?: string; created_at: string; lines: POLine[] };
type Movement = { id: number; movement_number: string; warehouse_id: number; warehouse_name: string; sku_id: number; sku_code: string; movement_type: string; quantity: number; before_quantity: number; after_quantity: number; reference_type: string; reference_id?: number; note?: string; created_at: string };
type DraftLine = { sku_id: string; quantity: number; unit_price_rmb: string };

const money = (value: number | string) => `¥${Number(value || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const dateTime = (value: string) => new Date(value).toLocaleString('zh-CN', { hour12: false });
const statusLabels: Record<string, string> = { draft: '草稿', ordered: '待收货', partially_received: '部分入库', received: '已完成', cancelled: '已取消' };
const movementLabels: Record<string, string> = { purchase_in: '采购入库', adjustment: '库存调整', sale_out: '销售出库', reservation: '库存锁定', release: '释放锁定' };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API}${path}`, { ...init, cache: 'no-store', headers: { ...(init?.body ? { 'Content-Type': 'application/json' } : {}), ...init?.headers } });
  } catch {
    throw new Error('无法连接后端 API。请确认 FastAPI 已启动，并检查 NEXT_PUBLIC_API_URL。');
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload?.detail;
    throw new Error(typeof detail === 'string' ? detail : `请求失败（HTTP ${response.status}）`);
  }
  return payload as T;
}

export default function ProcurementPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [movements, setMovements] = useState<Movement[]>([]);
  const [receipts, setReceipts] = useState<any[]>([]);
  const [supplierId, setSupplierId] = useState('');
  const [warehouseId, setWarehouseId] = useState('');
  const [expectedAt, setExpectedAt] = useState('');
  const [note, setNote] = useState('');
  const [draftLines, setDraftLines] = useState<DraftLine[]>([{ sku_id: '', quantity: '100', unit_price_rmb: '10.00' }]);
  const [receiptQty, setReceiptQty] = useState<Record<number, number>>({});
  const [statusFilter, setStatusFilter] = useState('');
  const [movementWarehouse, setMovementWarehouse] = useState('');
  const [movementSku, setMovementSku] = useState('');
  const [activeTab, setActiveTab] = useState<'orders' | 'receipts' | 'ledger'>('orders');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const allSkus = useMemo(() => products.flatMap(product => product.skus.map(sku => ({ ...sku, productName: product.name_cn, spu: product.spu_code }))), [products]);
  const totalOrders = orders.length;
  const openOrders = orders.filter(order => ['ordered', 'partially_received'].includes(order.status)).length;
  const totalPending = orders.reduce((sum, order) => sum + order.lines.reduce((lineSum, line) => lineSum + line.remaining_quantity, 0), 0);
  const totalReceived = receipts.length;

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [supplierData, warehouseData, productData, orderData, movementData, receiptData] = await Promise.all([
        request<Supplier[]>('/api/v1/suppliers'), request<Warehouse[]>('/api/v1/warehouses'),
        request<Product[]>('/api/v1/products?limit=200'), request<PurchaseOrder[]>('/api/v1/purchase-orders?limit=200'),
        request<Movement[]>('/api/v1/inventory/movements?limit=500'), request<any[]>('/api/v1/goods-receipts?limit=200'),
      ]);
      setSuppliers(supplierData); setWarehouses(warehouseData); setProducts(productData);
      setOrders(orderData); setMovements(movementData); setReceipts(receiptData);
      setSupplierId(current => current || String(supplierData[0]?.id || ''));
      setWarehouseId(current => current || String(warehouseData[0]?.id || ''));
      setDraftLines(current => current.map((line, index) => ({ ...line, sku_id: line.sku_id || String(productData.flatMap(p => p.skus)[index]?.id || productData.flatMap(p => p.skus)[0]?.id || '') })));
    } catch (e) { setError(e instanceof Error ? e.message : '加载数据失败'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function runAction(action: () => Promise<string>) {
    setSaving(true); setError(''); setSuccess('');
    try { setSuccess(await action()); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : '操作失败'); }
    finally { setSaving(false); }
  }

  function updateLine(index: number, key: keyof DraftLine, value: string) {
    setDraftLines(lines => lines.map((line, i) => i === index ? { ...line, [key]: value } : line));
  }
  function addLine() { setDraftLines(lines => [...lines, { sku_id: allSkus[0] ? String(allSkus[0].id) : '', quantity: '1', unit_price_rmb: '0.01' }]); }
  function removeLine(index: number) { setDraftLines(lines => lines.length > 1 ? lines.filter((_, i) => i !== index) : lines); }

  async function createOrder(event: FormEvent) {
    event.preventDefault();
    if (!supplierId || !warehouseId || !draftLines.every(line => line.sku_id && Number(line.quantity) > 0 && Number(line.unit_price_rmb) > 0)) {
      setError('请完整填写供应商、仓库、SKU、正数采购数量和单价。'); return;
    }
    await runAction(async () => {
      const created = await request<PurchaseOrder>('/api/v1/purchase-orders', { method: 'POST', body: JSON.stringify({ supplier_id: Number(supplierId), warehouse_id: Number(warehouseId), expected_at: expectedAt ? `${expectedAt}T00:00:00` : null, note, lines: draftLines.map(line => ({ sku_id: Number(line.sku_id), quantity: Number(line.quantity), unit_price_rmb: Number(line.unit_price_rmb) })) }) });
      setNote(''); setExpectedAt(''); setDraftLines([{ sku_id: allSkus[0] ? String(allSkus[0].id) : '', quantity: '100', unit_price_rmb: '10.00' }]);
      return `采购单 ${created.po_number} 已创建`;
    });
  }

  async function submitOrder(id: number) { await runAction(async () => { await request(`/api/v1/purchase-orders/${id}/submit`, { method: 'POST' }); return '采购单已提交，等待到货'; }); }
  async function cancelOrder(id: number) { if (!window.confirm('确定取消这张采购单？取消后不能继续入库。')) return; await runAction(async () => { await request(`/api/v1/purchase-orders/${id}/cancel`, { method: 'POST' }); return '采购单已取消'; }); }
  async function receiveOrder(order: PurchaseOrder) {
    const lines = order.lines.map(line => ({ line, quantity: Number(receiptQty[line.id] ?? line.remaining_quantity) })).filter(item => item.quantity > 0);
    if (!lines.length) { setError('请输入至少一条大于 0 的本次入库数量。'); return; }
    if (lines.some(item => item.quantity > item.line.remaining_quantity)) { setError('本次入库数量不能超过待入库数量。'); return; }
    await runAction(async () => {
      const result = await request<{ receipt_number: string }>('/api/v1/goods-receipts', { method: 'POST', body: JSON.stringify({ purchase_order_id: order.id, note: 'Rain ERP v0.5 采购收货', lines: lines.map(item => ({ purchase_order_line_id: item.line.id, quantity: item.quantity })) }) });
      return `入库单 ${result.receipt_number} 已完成，库存与流水已同步`;
    });
  }

  const filteredOrders = orders.filter(order => !statusFilter || order.status === statusFilter);
  const filteredMovements = movements.filter(row => (!movementWarehouse || String(row.warehouse_id) === movementWarehouse) && (!movementSku || String(row.sku_id) === movementSku));
  const selectStyle: CSSProperties = { width: '100%', border: '1px solid #dfe3e8', borderRadius: 7, padding: '9px 10px', background: '#fff', color: '#17243a', minWidth: 0 };
  const inputStyle: CSSProperties = { ...selectStyle };

  return <div className="shell">
    <aside className="sidebar"><Link href="/" className="brand" style={{ textDecoration: 'none' }}>RAIN<span> CROSS-BORDER ERP</span></Link><nav className="nav"><Link className="navLink" href="/">▦　经营总览</Link><Link className="navLink" href="/">▤　商品管理</Link><Link className="navLink" href="/">♧　供应商管理</Link><Link className="navLink" href="/procurement" style={{ background: '#1e293b', color: '#fff' }}>⇄　采购与入库</Link></nav><div className="sideFoot">RAIN ERP · VERSION 0.5<br/>采购、收货与库存账本</div></aside>
    <div className="main"><header className="top"><div><div className="eyebrow">SUPPLY CHAIN / PROCUREMENT</div><strong>采购管理</strong></div><div style={{ display: 'flex', alignItems: 'center', gap: 12 }}><span className="muted">业务数据实时读取</span><button className="btn" onClick={() => void load()} disabled={loading}>↻ 刷新数据</button></div></header>
      <main className="content">
        <div className="sectionHead"><div><h1>采购与入库工作台</h1><p>从采购下单、供应商交付到仓库收货，库存变动自动记账。</p></div><span className="badge">API 已连接时显示实时数据</span></div>
        {(error || success) && <div role="alert" className="notice" style={{ background: error ? '#fef2f2' : '#ecfdf5', color: error ? '#b91c1c' : '#047857', marginBottom: 16 }}>{error || success}</div>}
        <section className="metricRow">
          <div className="card metricCard"><div className="metricIcon">▤</div><div><div className="muted">采购单总数</div><div className="metricValue">{totalOrders}</div></div></div>
          <div className="card metricCard"><div className="metricIcon">⇄</div><div><div className="muted">待收货采购单</div><div className="metricValue">{openOrders}</div></div></div>
          <div className="card metricCard"><div className="metricIcon">▦</div><div><div className="muted">待入库总件数</div><div className="metricValue">{totalPending.toLocaleString()}</div></div></div>
        </section>

        <section className="card" style={{ marginBottom: 18 }}><div className="tableTitle"><h2>新建采购单</h2><span>支持一张采购单添加多个 SKU</span></div>
          <form onSubmit={createOrder}>
            <div className="row" style={{ marginBottom: 14 }}>
              <div className="field"><label>供应商</label><select style={selectStyle} value={supplierId} onChange={e => setSupplierId(e.target.value)}><option value="">选择供应商</option>{suppliers.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select></div>
              <div className="field"><label>收货仓库</label><select style={selectStyle} value={warehouseId} onChange={e => setWarehouseId(e.target.value)}><option value="">选择仓库</option>{warehouses.map(x => <option key={x.id} value={x.id}>{x.name} ({x.code})</option>)}</select></div>
              <div className="field"><label>预计到货日期</label><input style={inputStyle} type="date" value={expectedAt} onChange={e => setExpectedAt(e.target.value)} /></div>
              <div className="field" style={{ flex: 2 }}><label>采购备注</label><input style={inputStyle} value={note} onChange={e => setNote(e.target.value)} placeholder="例如：海运补货 / 供应商交期说明" /></div>
            </div>
            <div className="tableScroll" style={{ marginBottom: 12 }}><table><thead><tr><th style={{ minWidth: 240 }}>SKU / 商品</th><th>采购数量</th><th>含税单价（RMB）</th><th>小计</th><th>操作</th></tr></thead><tbody>{draftLines.map((line, index) => <tr key={index}><td><select style={selectStyle} value={line.sku_id} onChange={e => updateLine(index, 'sku_id', e.target.value)}><option value="">选择 SKU</option>{allSkus.map(sku => <option key={sku.id} value={sku.id}>{sku.sku_code} · {sku.productName}</option>)}</select></td><td><input style={{ ...inputStyle, width: 110 }} type="number" min="1" step="1" value={line.quantity} onChange={e => updateLine(index, 'quantity', e.target.value)} /></td><td><input style={{ ...inputStyle, width: 130 }} type="number" min="0.01" step="0.01" value={line.unit_price_rmb} onChange={e => updateLine(index, 'unit_price_rmb', e.target.value)} /></td><td><strong>{money(Number(line.quantity) * Number(line.unit_price_rmb))}</strong></td><td><button type="button" className="btn danger" onClick={() => removeLine(index)} disabled={draftLines.length === 1}>移除</button></td></tr>)}</tbody></table></div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}><button type="button" className="btn" onClick={addLine} disabled={!allSkus.length}>＋ 添加 SKU</button><div style={{ display: 'flex', alignItems: 'center', gap: 14 }}><span className="muted">采购总额 <strong style={{ color: '#17243a', fontSize: 18 }}>{money(draftLines.reduce((sum, line) => sum + Number(line.quantity || 0) * Number(line.unit_price_rmb || 0), 0))}</strong></span><button type="submit" className="btn primary" disabled={saving || !suppliers.length || !warehouses.length || !allSkus.length}>{saving ? '处理中…' : '创建采购草稿'}</button></div></div>
            {(!suppliers.length || !warehouses.length || !allSkus.length) && <p className="notice">请先在商品管理、供应商管理和仓库管理中建立基础资料，再创建采购单。</p>}
          </form>
        </section>

        <section className="card tableCard" style={{ marginTop: 0 }}><div className="tableTitle"><div><h2>采购业务记录</h2><p className="muted" style={{ marginTop: 5 }}>采购订单、收货记录与库存流水</p></div><div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>{(['orders', 'receipts', 'ledger'] as const).map(tab => <button key={tab} className={`btn ${activeTab === tab ? 'primary' : ''}`} onClick={() => setActiveTab(tab)}>{tab === 'orders' ? '采购单' : tab === 'receipts' ? '入库记录' : '库存流水'}</button>)}</div></div>
          {activeTab === 'orders' && <><div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 10 }}><select className="btn" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}><option value="">全部状态</option>{Object.entries(statusLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></div><div className="tableScroll"><table><thead><tr><th>采购单号 / 创建时间</th><th>供应商</th><th>收货仓</th><th>SKU</th><th>采购数量</th><th>已入库</th><th>待入库</th><th>采购金额</th><th>状态</th><th>操作</th></tr></thead><tbody>{filteredOrders.flatMap(order => order.lines.map((line, index) => <tr key={`${order.id}-${line.id}`}><td><strong>{index === 0 ? order.po_number : ''}</strong><div className="muted">{index === 0 ? dateTime(order.created_at) : ''}</div></td><td>{index === 0 ? order.supplier_name : ''}</td><td>{index === 0 ? order.warehouse_name : ''}</td><td>{line.sku_code}</td><td>{line.quantity}</td><td>{line.received_quantity}</td><td><strong>{line.remaining_quantity}</strong></td><td>{money(line.line_total_rmb)}</td><td><span className={order.status === 'received' ? 'badge' : 'muted'}>{statusLabels[order.status] || order.status}</span></td><td>{index === 0 && <div style={{ display: 'flex', gap: 6 }}>{order.status === 'draft' && <><button className="btn primary" disabled={saving} onClick={() => void submitOrder(order.id)}>提交</button><button className="btn danger" disabled={saving} onClick={() => void cancelOrder(order.id)}>取消</button></>}{['ordered', 'partially_received'].includes(order.status) && <button className="btn primary" disabled={saving} onClick={() => void receiveOrder(order)}>确认入库</button>}</div>}{['ordered', 'partially_received'].includes(order.status) && <div style={{ display: 'flex', gap: 4, marginTop: 5 }}>{order.lines.map(item => <label key={item.id} title={`${item.sku_code} 本次入库数量`}><input aria-label={`${item.sku_code} 本次入库数量`} type="number" min="0" max={item.remaining_quantity} value={receiptQty[item.id] ?? item.remaining_quantity} onChange={e => setReceiptQty(current => ({ ...current, [item.id]: Number(e.target.value) }))} style={{ width: 76, padding: 5, border: '1px solid #dfe3e8', borderRadius: 5 }} /></label>)}</div>}</td></tr>))}</tbody></table>{!filteredOrders.length && <div className="empty">{loading ? '正在加载采购单…' : '暂无符合条件的采购单'}</div>}</div></>}
          {activeTab === 'receipts' && <div className="tableScroll"><table><thead><tr><th>入库单号</th><th>关联采购单 ID</th><th>仓库 ID</th><th>入库时间</th><th>备注</th></tr></thead><tbody>{receipts.map(row => <tr key={row.id}><td><strong>{row.receipt_number}</strong></td><td>{row.purchase_order_id}</td><td>{row.warehouse_id}</td><td>{dateTime(row.received_at)}</td><td>{row.note || '—'}</td></tr>)}</tbody></table>{!receipts.length && <div className="empty">暂无入库记录</div>}</div>}
          {activeTab === 'ledger' && <><div className="row" style={{ marginBottom: 12 }}><div className="field"><label>按仓库筛选</label><select style={selectStyle} value={movementWarehouse} onChange={e => setMovementWarehouse(e.target.value)}><option value="">全部仓库</option>{warehouses.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select></div><div className="field"><label>按 SKU 筛选</label><select style={selectStyle} value={movementSku} onChange={e => setMovementSku(e.target.value)}><option value="">全部 SKU</option>{allSkus.map(x => <option key={x.id} value={x.id}>{x.sku_code}</option>)}</select></div></div><div className="tableScroll"><table><thead><tr><th>流水号 / 时间</th><th>仓库</th><th>SKU</th><th>变动类型</th><th>变动数量</th><th>变动前</th><th>变动后</th><th>业务来源</th><th>备注</th></tr></thead><tbody>{filteredMovements.map(row => <tr key={row.id}><td><strong>{row.movement_number}</strong><div className="muted">{dateTime(row.created_at)}</div></td><td>{row.warehouse_name}</td><td>{row.sku_code}</td><td>{movementLabels[row.movement_type] || row.movement_type}</td><td style={{ color: row.quantity >= 0 ? '#047857' : '#b91c1c', fontWeight: 700 }}>{row.quantity > 0 ? '+' : ''}{row.quantity}</td><td>{row.before_quantity}</td><td><strong>{row.after_quantity}</strong></td><td>{row.reference_type}{row.reference_id ? ` #${row.reference_id}` : ''}</td><td>{row.note || '—'}</td></tr>)}</tbody></table>{!filteredMovements.length && <div className="empty">暂无库存流水</div>}</div></>}
        </section>
        <p className="muted" style={{ textAlign: 'center', padding: '18px 0' }}>Rain ERP v0.5 · 采购入库与库存流水 · {totalReceived} 笔收货记录</p>
      </main>
    </div>
  </div>;
}
