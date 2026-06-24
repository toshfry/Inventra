from sqlalchemy.orm import Session
from database.models.supplier import Supplier
from core.validators.supplier_schema import SupplierCreate, SupplierUpdate
from datetime import datetime


class SupplierService:

    def __init__(self, db: Session):
        self.db = db

    def get_all(self, include_inactive: bool = False):
        q = self.db.query(Supplier)
        if not include_inactive:
            q = q.filter(Supplier.is_active == 1)
        return q.order_by(Supplier.name).all()

    def get_by_id(self, supplier_id: int) -> Supplier:
        return self.db.query(Supplier).filter(Supplier.id == supplier_id).first()

    def create(self, data: SupplierCreate) -> Supplier:
        supplier = Supplier(
            name=data.name,
            contact_name=data.contact_name,
            phone=data.phone,
            email=data.email,
            address=data.address,
            notes=data.notes,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        self.db.add(supplier)
        self.db.commit()
        self.db.refresh(supplier)
        return supplier

    def update(self, supplier_id: int, data: SupplierUpdate) -> Supplier:
        supplier = self.get_by_id(supplier_id)
        if not supplier:
            raise ValueError(f"Supplier {supplier_id} not found")
        updates = data.model_dump(exclude_none=True)
        for k, v in updates.items():
            setattr(supplier, k, v)
        supplier.updated_at = datetime.now().isoformat()
        self.db.commit()
        self.db.refresh(supplier)
        return supplier

    def deactivate(self, supplier_id: int):
        supplier = self.get_by_id(supplier_id)
        if not supplier:
            raise ValueError(f"Supplier {supplier_id} not found")
        supplier.is_active = 0
        supplier.updated_at = datetime.now().isoformat()
        self.db.commit()
        return supplier

    def delete(self, supplier_id: int):
        """
        Delete from the user's point of view.

        This uses soft-delete/deactivate so old stock-in history and reports
        still remain safe.
        """
        return self.deactivate(supplier_id)
