from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict

class SKUBase(BaseModel):
    sku_code: str = Field(min_length=1, max_length=64)
    purchase_price_rmb: Decimal = Field(gt=0)
    length_cm: Decimal = Field(gt=0)
    width_cm: Decimal = Field(gt=0)
    height_cm: Decimal = Field(gt=0)
    weight_g: Decimal = Field(gt=0)

class SKUCreate(SKUBase): pass
class SKUResponse(SKUBase):
    id: int
    active: bool
    model_config = ConfigDict(from_attributes=True)

class ProductCreate(BaseModel):
    spu_code: str = Field(min_length=1, max_length=64)
    name_cn: str = Field(min_length=1, max_length=200)
    name_en: str | None = None
    category: str | None = None
    main_image_url: str | None = None
    supplier_url: str | None = None
    skus: list[SKUCreate] = Field(min_length=1, max_length=50)
class ProductResponse(BaseModel):
    id: int; spu_code: str; name_cn: str; name_en: str | None; category: str | None
    main_image_url: str | None; supplier_url: str | None; skus: list[SKUResponse]

class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    platform: str = Field(default='1688', max_length=50)
    url: str | None = None
    contact: str | None = None
    note: str | None = None
class SupplierResponse(SupplierCreate):
    id: int; active: bool
    model_config = ConfigDict(from_attributes=True)

class QuoteCreate(BaseModel):
    supplier_id: int = Field(gt=0); sku_id: int = Field(gt=0)
    unit_price_rmb: Decimal = Field(gt=0); moq: int = Field(default=1, ge=1); lead_days: int = Field(default=7, ge=0)
class WarehouseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32); name: str = Field(min_length=1, max_length=100)
    warehouse_type: str = 'domestic'; country: str = 'CN'
class InventoryUpsert(BaseModel):
    warehouse_id: int = Field(gt=0); sku_id: int = Field(gt=0)
    on_hand: int = Field(default=0, ge=0); reserved: int = Field(default=0, ge=0); in_transit: int = Field(default=0, ge=0)

class OrderCreate(BaseModel):
    store_id: str; platform_order_id: str; order_status: str = 'pending'; total_amount_usd: Decimal = Field(gt=0)
    tracking_number: str | None = None; ordered_at: datetime | None = None
class ProfitRequest(BaseModel):
    purchase_cost_rmb: Decimal = Field(gt=0); freight_cost_rmb: Decimal = Field(ge=0, default=Decimal('0'))
    other_cost_rmb: Decimal = Field(ge=0, default=Decimal('0')); price_usd: Decimal = Field(gt=0)
    exchange_rate: Decimal = Field(gt=0); commission_rate: Decimal = Field(ge=0, lt=1)

class PurchaseOrderLineCreate(BaseModel):
    sku_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    unit_price_rmb: Decimal = Field(gt=0)
class PurchaseOrderCreate(BaseModel):
    supplier_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    expected_at: datetime | None = None
    note: str | None = None
    lines: list[PurchaseOrderLineCreate] = Field(min_length=1, max_length=200)
class ReceiptLineCreate(BaseModel):
    purchase_order_line_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
class GoodsReceiptCreate(BaseModel):
    purchase_order_id: int = Field(gt=0)
    note: str | None = None
    lines: list[ReceiptLineCreate] = Field(min_length=1, max_length=200)
class InventoryAdjustment(BaseModel):
    warehouse_id: int = Field(gt=0)
    sku_id: int = Field(gt=0)
    quantity: int
    note: str = Field(min_length=1, max_length=500)
