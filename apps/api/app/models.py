from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

class SPUProduct(Base):
    __tablename__ = 'spu_products'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    spu_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name_cn: Mapped[str] = mapped_column(String(200))
    name_en: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    main_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    supplier_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, server_default=func.now())
    skus: Mapped[list['SKUVariant']] = relationship(back_populates='spu', cascade='all, delete-orphan')

class SKUVariant(Base):
    __tablename__ = 'sku_variants'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    spu_id: Mapped[int] = mapped_column(ForeignKey('spu_products.id', ondelete='CASCADE'), index=True)
    sku_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    purchase_price_rmb: Mapped[object] = mapped_column(Numeric(12, 2))
    length_cm: Mapped[object] = mapped_column(Numeric(10, 2))
    width_cm: Mapped[object] = mapped_column(Numeric(10, 2))
    height_cm: Mapped[object] = mapped_column(Numeric(10, 2))
    weight_g: Mapped[object] = mapped_column(Numeric(10, 2))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    spu: Mapped[SPUProduct] = relationship(back_populates='skus')
    inventories: Mapped[list['Inventory']] = relationship(back_populates='sku', cascade='all, delete-orphan')

class Supplier(Base):
    __tablename__ = 'suppliers'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    platform: Mapped[str | None] = mapped_column(String(50), nullable=True, default='1688')
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact: Mapped[str | None] = mapped_column(String(100), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    quotes: Mapped[list['SupplierQuote']] = relationship(back_populates='supplier', cascade='all, delete-orphan')

class SupplierQuote(Base):
    __tablename__ = 'supplier_quotes'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey('suppliers.id', ondelete='CASCADE'), index=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey('sku_variants.id', ondelete='CASCADE'), index=True)
    unit_price_rmb: Mapped[object] = mapped_column(Numeric(12, 2))
    moq: Mapped[int] = mapped_column(Integer, default=1)
    lead_days: Mapped[int] = mapped_column(Integer, default=7)
    updated_at: Mapped[object] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    supplier: Mapped[Supplier] = relationship(back_populates='quotes')

class Warehouse(Base):
    __tablename__ = 'warehouses'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    warehouse_type: Mapped[str] = mapped_column(String(30), default='domestic')
    country: Mapped[str] = mapped_column(String(60), default='CN')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    inventories: Mapped[list['Inventory']] = relationship(back_populates='warehouse', cascade='all, delete-orphan')

class Inventory(Base):
    __tablename__ = 'inventory'
    __table_args__ = (UniqueConstraint('warehouse_id', 'sku_id', name='uq_inventory_warehouse_sku'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey('warehouses.id', ondelete='CASCADE'), index=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey('sku_variants.id', ondelete='CASCADE'), index=True)
    on_hand: Mapped[int] = mapped_column(Integer, default=0)
    reserved: Mapped[int] = mapped_column(Integer, default=0)
    in_transit: Mapped[int] = mapped_column(Integer, default=0)
    warehouse: Mapped[Warehouse] = relationship(back_populates='inventories')
    sku: Mapped[SKUVariant] = relationship(back_populates='inventories')

class Order(Base):
    __tablename__ = 'orders'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[str] = mapped_column(String(64), index=True)
    platform_order_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    order_status: Mapped[str] = mapped_column(String(32), default='pending')
    total_amount_usd: Mapped[object] = mapped_column(Numeric(12, 2))
    tracking_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ordered_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)

class PurchaseOrder(Base):
    __tablename__ = 'purchase_orders'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    po_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey('suppliers.id'), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey('warehouses.id'), index=True)
    status: Mapped[str] = mapped_column(String(20), default='draft', index=True)
    currency: Mapped[str] = mapped_column(String(3), default='CNY')
    expected_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, server_default=func.now())
    lines: Mapped[list['PurchaseOrderLine']] = relationship(back_populates='purchase_order', cascade='all, delete-orphan')

class PurchaseOrderLine(Base):
    __tablename__ = 'purchase_order_lines'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey('purchase_orders.id', ondelete='CASCADE'), index=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey('sku_variants.id'), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    received_quantity: Mapped[int] = mapped_column(Integer, default=0)
    unit_price_rmb: Mapped[object] = mapped_column(Numeric(12, 2))
    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates='lines')
    sku: Mapped[SKUVariant] = relationship()

class GoodsReceipt(Base):
    __tablename__ = 'goods_receipts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey('purchase_orders.id'), index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey('warehouses.id'), index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[object] = mapped_column(DateTime, server_default=func.now())

class InventoryMovement(Base):
    __tablename__ = 'inventory_movements'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    movement_number: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey('warehouses.id'), index=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey('sku_variants.id'), index=True)
    movement_type: Mapped[str] = mapped_column(String(24), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    before_quantity: Mapped[int] = mapped_column(Integer)
    after_quantity: Mapped[int] = mapped_column(Integer)
    reference_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reference_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, server_default=func.now(), index=True)
# Relationships declared after class definitions to keep the v0.4 schema intact.
PurchaseOrder.supplier = relationship(Supplier)
PurchaseOrder.warehouse = relationship(Warehouse)
InventoryMovement.sku = relationship(SKUVariant)
InventoryMovement.warehouse = relationship(Warehouse)
