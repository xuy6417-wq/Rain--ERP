from decimal import Decimal
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import os
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from .db import Base, engine, get_db
from .models import SPUProduct, SKUVariant, Order, Supplier, SupplierQuote, Warehouse, Inventory, PurchaseOrder, PurchaseOrderLine, GoodsReceipt, InventoryMovement
from .schemas import ProductCreate, ProductResponse, OrderCreate, ProfitRequest, SupplierCreate, SupplierResponse, QuoteCreate, WarehouseCreate, InventoryUpsert, PurchaseOrderCreate, GoodsReceiptCreate, InventoryAdjustment

app = FastAPI(title='Rain ERP API', version='0.5.0')
_origins = os.getenv('CORS_ALLOW_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in _origins if x.strip()], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

@app.on_event('startup')
def startup(): Base.metadata.create_all(bind=engine)

def shipping(sku, sea_rmb_per_cbm=Decimal('1200')):
    volume = sku.length_cm * sku.width_cm * sku.height_cm
    cbm = volume / Decimal('1000000')
    return volume, cbm, cbm * Decimal(str(sea_rmb_per_cbm))

def product_response(p): return ProductResponse(id=p.id, spu_code=p.spu_code, name_cn=p.name_cn, name_en=p.name_en, category=p.category, main_image_url=p.main_image_url, supplier_url=p.supplier_url, skus=p.skus)

def conflict(msg): raise HTTPException(409, msg)

@app.get('/health')
def health(): return {'status':'ok','service':'rain-api','version':'0.5.0'}

@app.post('/api/v1/products', response_model=ProductResponse, status_code=201)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    if db.scalar(select(SPUProduct).where(SPUProduct.spu_code == payload.spu_code)): conflict('SPU code already exists')
    codes = [x.sku_code for x in payload.skus]
    if len(codes) != len(set(codes)): raise HTTPException(422, 'SKU codes must be unique within the product')
    if db.scalar(select(SKUVariant).where(SKUVariant.sku_code.in_(codes))): conflict('One or more SKU codes already exist')
    spu = SPUProduct(spu_code=payload.spu_code, name_cn=payload.name_cn, name_en=payload.name_en, category=payload.category, main_image_url=payload.main_image_url, supplier_url=payload.supplier_url)
    spu.skus = [SKUVariant(**sku.model_dump()) for sku in payload.skus]; db.add(spu)
    try: db.commit()
    except IntegrityError: db.rollback(); conflict('Product or SKU code already exists')
    db.refresh(spu); return product_response(spu)

@app.get('/api/v1/products', response_model=list[ProductResponse])
def list_products(q: str | None = Query(None, max_length=100), limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    stmt = select(SPUProduct).options(selectinload(SPUProduct.skus)).order_by(SPUProduct.id.desc()).limit(limit)
    if q:
        like=f'%{q}%'; stmt=select(SPUProduct).options(selectinload(SPUProduct.skus)).where((SPUProduct.spu_code.ilike(like))|(SPUProduct.name_cn.ilike(like))).order_by(SPUProduct.id.desc()).limit(limit)
    return [product_response(p) for p in db.scalars(stmt).unique().all()]

@app.get('/api/v1/products/{product_id}', response_model=ProductResponse)
def get_product(product_id:int, db:Session=Depends(get_db)):
    p=db.scalar(select(SPUProduct).options(selectinload(SPUProduct.skus)).where(SPUProduct.id==product_id))
    if not p: raise HTTPException(404,'Product not found')
    return product_response(p)

@app.delete('/api/v1/products/{product_id}', status_code=204)
def delete_product(product_id:int, db:Session=Depends(get_db)):
    p=db.get(SPUProduct,product_id)
    if not p: raise HTTPException(404,'Product not found')
    db.delete(p); db.commit()

@app.post('/api/v1/profit/calculate')
def calculate_profit(payload:ProfitRequest):
    revenue=payload.price_usd*payload.exchange_rate; commission=revenue*payload.commission_rate
    total_cost=payload.purchase_cost_rmb+payload.freight_cost_rmb+payload.other_cost_rmb; profit=revenue-commission-total_cost
    return {'revenue_rmb':revenue,'commission_rmb':commission,'total_cost_rmb':total_cost,'profit_rmb':profit,'margin':profit/revenue if revenue else Decimal('0')}

@app.post('/api/v1/suppliers', response_model=SupplierResponse, status_code=201)
def create_supplier(payload:SupplierCreate, db:Session=Depends(get_db)):
    if db.scalar(select(Supplier).where(Supplier.name==payload.name)): conflict('Supplier already exists')
    row=Supplier(**payload.model_dump()); db.add(row); db.commit(); db.refresh(row); return row

@app.get('/api/v1/suppliers', response_model=list[SupplierResponse])
def list_suppliers(db:Session=Depends(get_db)):
    return db.scalars(select(Supplier).where(Supplier.active.is_(True)).order_by(Supplier.id.desc())).all()

@app.post('/api/v1/supplier-quotes', status_code=201)
def create_quote(payload:QuoteCreate, db:Session=Depends(get_db)):
    if not db.get(Supplier,payload.supplier_id): raise HTTPException(404,'Supplier not found')
    if not db.get(SKUVariant,payload.sku_id): raise HTTPException(404,'SKU not found')
    row=SupplierQuote(**payload.model_dump()); db.add(row); db.commit(); db.refresh(row)
    return {'id':row.id, **payload.model_dump(mode='json')}

@app.get('/api/v1/supplier-quotes')
def list_quotes(limit:int=Query(100,ge=1,le=500), db:Session=Depends(get_db)):
    rows=db.scalars(select(SupplierQuote).order_by(SupplierQuote.id.desc()).limit(limit)).all()
    return [{'id':x.id,'supplier_id':x.supplier_id,'sku_id':x.sku_id,'unit_price_rmb':str(x.unit_price_rmb),'moq':x.moq,'lead_days':x.lead_days} for x in rows]

@app.post('/api/v1/warehouses', status_code=201)
def create_warehouse(payload:WarehouseCreate, db:Session=Depends(get_db)):
    if db.scalar(select(Warehouse).where(Warehouse.code==payload.code)): conflict('Warehouse code already exists')
    row=Warehouse(**payload.model_dump()); db.add(row); db.commit(); db.refresh(row); return {'id':row.id,**payload.model_dump()}

@app.get('/api/v1/warehouses')
def list_warehouses(db:Session=Depends(get_db)):
    return db.scalars(select(Warehouse).where(Warehouse.active.is_(True)).order_by(Warehouse.id)).all()

@app.put('/api/v1/inventory', status_code=200)
def upsert_inventory(payload:InventoryUpsert, db:Session=Depends(get_db)):
    if not db.get(Warehouse,payload.warehouse_id): raise HTTPException(404,'Warehouse not found')
    if not db.get(SKUVariant,payload.sku_id): raise HTTPException(404,'SKU not found')
    row=db.scalar(select(Inventory).where(Inventory.warehouse_id==payload.warehouse_id, Inventory.sku_id==payload.sku_id))
    if not row: row=Inventory(**payload.model_dump()); db.add(row)
    else:
        for k,v in payload.model_dump().items(): setattr(row,k,v)
    db.commit(); db.refresh(row)
    return {'id':row.id,'warehouse_id':row.warehouse_id,'sku_id':row.sku_id,'on_hand':row.on_hand,'reserved':row.reserved,'in_transit':row.in_transit,'available':row.on_hand-row.reserved}

@app.get('/api/v1/inventory')
def list_inventory(limit:int=Query(200,ge=1,le=1000), db:Session=Depends(get_db)):
    rows=db.scalars(select(Inventory).options(selectinload(Inventory.sku),selectinload(Inventory.warehouse)).order_by(Inventory.id.desc()).limit(limit)).all()
    return [{'id':x.id,'warehouse_id':x.warehouse_id,'warehouse_code':x.warehouse.code,'warehouse_name':x.warehouse.name,'sku_id':x.sku_id,'sku_code':x.sku.sku_code,'on_hand':x.on_hand,'reserved':x.reserved,'in_transit':x.in_transit,'available':x.on_hand-x.reserved} for x in rows]

@app.post('/api/v1/orders', status_code=201)
def create_order(payload:OrderCreate, db:Session=Depends(get_db)):
    if db.scalar(select(Order).where(Order.platform_order_id==payload.platform_order_id)): conflict('Platform order already exists')
    order=Order(**payload.model_dump()); db.add(order); db.commit(); db.refresh(order); return {'id':order.id,**payload.model_dump(mode='json')}

@app.get('/api/v1/orders')
def list_orders(limit:int=Query(50,ge=1,le=200), db:Session=Depends(get_db)):
    rows=db.scalars(select(Order).order_by(Order.id.desc()).limit(limit)).all()
    return [{'id':x.id,'store_id':x.store_id,'platform_order_id':x.platform_order_id,'order_status':x.order_status,'total_amount_usd':str(x.total_amount_usd),'tracking_number':x.tracking_number,'ordered_at':x.ordered_at} for x in rows]


# ---- Procurement, receiving and immutable inventory ledger (v0.5) ----
def _po_dict(po):
    return {'id': po.id, 'po_number': po.po_number, 'supplier_id': po.supplier_id,
            'supplier_name': po.supplier.name if po.supplier else None,
            'warehouse_id': po.warehouse_id, 'warehouse_name': po.warehouse.name if po.warehouse else None,
            'status': po.status, 'currency': po.currency, 'expected_at': po.expected_at,
            'note': po.note, 'created_at': po.created_at,
            'lines': [{'id': x.id, 'sku_id': x.sku_id, 'sku_code': x.sku.sku_code,
                       'quantity': x.quantity, 'received_quantity': x.received_quantity,
                       'remaining_quantity': x.quantity-x.received_quantity,
                       'unit_price_rmb': str(x.unit_price_rmb),
                       'line_total_rmb': str(x.unit_price_rmb*x.quantity)} for x in po.lines]}

@app.post('/api/v1/purchase-orders', status_code=201)
def create_purchase_order(payload: PurchaseOrderCreate, db: Session = Depends(get_db)):
    if not db.get(Supplier, payload.supplier_id): raise HTTPException(404, 'Supplier not found')
    if not db.get(Warehouse, payload.warehouse_id): raise HTTPException(404, 'Warehouse not found')
    sku_ids = [x.sku_id for x in payload.lines]
    if len(sku_ids) != len(set(sku_ids)): raise HTTPException(422, 'Each SKU can appear only once per purchase order')
    for sku_id in sku_ids:
        if not db.get(SKUVariant, sku_id): raise HTTPException(404, f'SKU {sku_id} not found')
    po = PurchaseOrder(po_number=f"PO{__import__('datetime').datetime.now():%Y%m%d%H%M%S}{__import__('secrets').token_hex(2).upper()}",
        supplier_id=payload.supplier_id, warehouse_id=payload.warehouse_id,
        expected_at=payload.expected_at, note=payload.note, status='draft')
    po.lines = [PurchaseOrderLine(sku_id=x.sku_id, quantity=x.quantity, unit_price_rmb=x.unit_price_rmb) for x in payload.lines]
    db.add(po); db.commit()
    po = db.scalar(select(PurchaseOrder).options(selectinload(PurchaseOrder.lines).selectinload(PurchaseOrderLine.sku), selectinload(PurchaseOrder.supplier), selectinload(PurchaseOrder.warehouse)).where(PurchaseOrder.id==po.id))
    return _po_dict(po)

@app.get('/api/v1/purchase-orders')
def list_purchase_orders(status: str | None = None, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    stmt = select(PurchaseOrder).options(selectinload(PurchaseOrder.lines).selectinload(PurchaseOrderLine.sku), selectinload(PurchaseOrder.supplier), selectinload(PurchaseOrder.warehouse)).order_by(PurchaseOrder.id.desc()).limit(limit)
    if status: stmt = stmt.where(PurchaseOrder.status == status)
    return [_po_dict(x) for x in db.scalars(stmt).unique().all()]

@app.get('/api/v1/purchase-orders/{po_id}')
def get_purchase_order(po_id: int, db: Session = Depends(get_db)):
    po = db.scalar(select(PurchaseOrder).options(selectinload(PurchaseOrder.lines).selectinload(PurchaseOrderLine.sku), selectinload(PurchaseOrder.supplier), selectinload(PurchaseOrder.warehouse)).where(PurchaseOrder.id==po_id))
    if not po: raise HTTPException(404, 'Purchase order not found')
    return _po_dict(po)

@app.post('/api/v1/purchase-orders/{po_id}/submit')
def submit_purchase_order(po_id: int, db: Session = Depends(get_db)):
    po = db.scalar(select(PurchaseOrder).where(PurchaseOrder.id==po_id).with_for_update())
    if not po: raise HTTPException(404, 'Purchase order not found')
    if po.status != 'draft': raise HTTPException(409, 'Only draft purchase orders can be submitted')
    po.status = 'ordered'; db.commit(); return {'id': po.id, 'status': po.status}

@app.post('/api/v1/purchase-orders/{po_id}/cancel')
def cancel_purchase_order(po_id: int, db: Session = Depends(get_db)):
    po = db.scalar(select(PurchaseOrder).where(PurchaseOrder.id==po_id).with_for_update())
    if not po: raise HTTPException(404, 'Purchase order not found')
    if po.status not in ('draft', 'ordered'): raise HTTPException(409, 'Only draft or ordered purchase orders can be cancelled')
    po.status = 'cancelled'; db.commit(); return {'id': po.id, 'status': po.status}

@app.post('/api/v1/goods-receipts', status_code=201)
def create_goods_receipt(payload: GoodsReceiptCreate, db: Session = Depends(get_db)):
    po = db.scalar(select(PurchaseOrder).options(selectinload(PurchaseOrder.lines)).where(PurchaseOrder.id==payload.purchase_order_id).with_for_update())
    if not po: raise HTTPException(404, 'Purchase order not found')
    if po.status not in ('ordered', 'partially_received'): raise HTTPException(409, 'Purchase order must be submitted before receiving')
    line_map = {x.id: x for x in po.lines}
    seen = set()
    for item in payload.lines:
        if item.purchase_order_line_id in seen: raise HTTPException(422, 'Duplicate purchase order line in receipt')
        seen.add(item.purchase_order_line_id)
        line = line_map.get(item.purchase_order_line_id)
        if not line: raise HTTPException(422, 'Receipt line does not belong to this purchase order')
        if item.quantity > line.quantity-line.received_quantity: raise HTTPException(409, f'Over-receipt for SKU id {line.sku_id}')
    receipt = GoodsReceipt(receipt_number=f"GR{__import__('datetime').datetime.now():%Y%m%d%H%M%S}{__import__('secrets').token_hex(2).upper()}", purchase_order_id=po.id, warehouse_id=po.warehouse_id, note=payload.note)
    db.add(receipt); db.flush()
    for item in payload.lines:
        line = line_map[item.purchase_order_line_id]
        inv = db.scalar(select(Inventory).where(Inventory.warehouse_id==po.warehouse_id, Inventory.sku_id==line.sku_id).with_for_update())
        if not inv:
            inv = Inventory(warehouse_id=po.warehouse_id, sku_id=line.sku_id, on_hand=0, reserved=0, in_transit=0); db.add(inv); db.flush()
        before = inv.on_hand; inv.on_hand += item.quantity; line.received_quantity += item.quantity
        db.add(InventoryMovement(movement_number=f"IM{__import__('secrets').token_hex(10).upper()}", warehouse_id=po.warehouse_id, sku_id=line.sku_id, movement_type='purchase_in', quantity=item.quantity, before_quantity=before, after_quantity=inv.on_hand, reference_type='goods_receipt', reference_id=receipt.id, note=payload.note or f'Receipt {receipt.receipt_number}'))
    po.status = 'received' if all(x.received_quantity == x.quantity for x in po.lines) else 'partially_received'
    db.commit()
    return {'id': receipt.id, 'receipt_number': receipt.receipt_number, 'purchase_order_id': po.id, 'status': po.status, 'received_lines': len(payload.lines)}

@app.get('/api/v1/goods-receipts')
def list_goods_receipts(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    rows = db.scalars(select(GoodsReceipt).order_by(GoodsReceipt.id.desc()).limit(limit)).all()
    return [{'id':x.id,'receipt_number':x.receipt_number,'purchase_order_id':x.purchase_order_id,'warehouse_id':x.warehouse_id,'note':x.note,'received_at':x.received_at} for x in rows]

@app.post('/api/v1/inventory/adjustments', status_code=201)
def adjust_inventory(payload: InventoryAdjustment, db: Session = Depends(get_db)):
    if not db.get(Warehouse, payload.warehouse_id): raise HTTPException(404, 'Warehouse not found')
    if not db.get(SKUVariant, payload.sku_id): raise HTTPException(404, 'SKU not found')
    inv = db.scalar(select(Inventory).where(Inventory.warehouse_id==payload.warehouse_id, Inventory.sku_id==payload.sku_id).with_for_update())
    if not inv:
        if payload.quantity < 0: raise HTTPException(409, 'Cannot reduce stock below zero')
        inv = Inventory(warehouse_id=payload.warehouse_id, sku_id=payload.sku_id, on_hand=0, reserved=0, in_transit=0); db.add(inv); db.flush()
    before = inv.on_hand
    if before + payload.quantity < inv.reserved: raise HTTPException(409, 'Adjustment would make available stock negative')
    inv.on_hand += payload.quantity
    movement = InventoryMovement(movement_number=f"IM{__import__('secrets').token_hex(10).upper()}", warehouse_id=payload.warehouse_id, sku_id=payload.sku_id, movement_type='adjustment', quantity=payload.quantity, before_quantity=before, after_quantity=inv.on_hand, reference_type='manual_adjustment', note=payload.note)
    db.add(movement); db.commit(); db.refresh(movement)
    return {'id': movement.id, 'movement_number': movement.movement_number, 'before_quantity': before, 'after_quantity': inv.on_hand}

@app.get('/api/v1/inventory/movements')
def list_inventory_movements(warehouse_id: int | None = None, sku_id: int | None = None, limit: int = Query(200, ge=1, le=1000), db: Session = Depends(get_db)):
    stmt = select(InventoryMovement).options(selectinload(InventoryMovement.sku), selectinload(InventoryMovement.warehouse)).order_by(InventoryMovement.id.desc()).limit(limit)
    if warehouse_id: stmt = stmt.where(InventoryMovement.warehouse_id==warehouse_id)
    if sku_id: stmt = stmt.where(InventoryMovement.sku_id==sku_id)
    rows = db.scalars(stmt).all()
    return [{'id':x.id,'movement_number':x.movement_number,'warehouse_id':x.warehouse_id,'warehouse_code':x.warehouse.code,'warehouse_name':x.warehouse.name,'sku_id':x.sku_id,'sku_code':x.sku.sku_code,'movement_type':x.movement_type,'quantity':x.quantity,'before_quantity':x.before_quantity,'after_quantity':x.after_quantity,'reference_type':x.reference_type,'reference_id':x.reference_id,'note':x.note,'created_at':x.created_at} for x in rows]
