from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.deps import get_current_user,require_permissions,block_privilege_override
from app.core.rbac import Permission
from app.schemas.utility_pricing import PriceCreate
from app.services import utility_pricing_service as service

router=APIRouter(prefix='/api/utility-pricing',tags=['Utility pricing'],dependencies=[Depends(get_current_user),Depends(block_privilege_override)])

@router.post('/history',status_code=201)
def create(data:PriceCreate,db:Session=Depends(get_db),user=Depends(require_permissions(Permission.UTILITY_MANAGE))):
    return service.create_price(db,user,data)

@router.get('/history')
def history(property_id:int,db:Session=Depends(get_db),user=Depends(require_permissions(Permission.UTILITY_MANAGE))):
    return service.list_prices(db,user,property_id)

@router.get('/preview')
def preview(contract_id:int,period:str,db:Session=Depends(get_db),user=Depends(require_permissions(Permission.UTILITY_MANAGE))):
    return service.calculate(db,user,contract_id,period)
