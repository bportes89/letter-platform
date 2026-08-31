import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Contract, EarlySettlementQuote, FinOpsDomainEvent, User

CENT=Decimal("0.01");HUNDRED=Decimal("100")
SUPPORTED_EVENTS={
 "invoice.past_due_lock":"SAFE_HOLD_PENDING_OFFICIAL_BAAS",
 "asset.extrajudicial_notice":"DOCUMENT_PENDING_LEGAL_AND_REGISTRY_REVIEW",
 "asset.caducidade_countdown":"INFORMATIONAL_COUNTDOWN_NO_AUTOMATIC_LOSS",
 "asset.caducidade_executed":"BLOCKED_REQUIRES_DUAL_LEGAL_APPROVAL",
 "sdc.reservation.timeout":"INVENTORY_RELEASE_PENDING_RECONCILIATION",
 "sdc.bullet.settlement":"SETTLEMENT_RECORDED_PENDING_RECONCILIATION",
 "sdc.mmn.split":"COMMISSION_PREVIEW_PENDING_FISCAL",
 "sdc.provider.payout":"BLOCKED_PENDING_BIOMETRY_AND_DUAL_APPROVAL",
 "tapaf.payment.settled":"TAPAF_SPLIT_POSTED_PENDING_RECONCILIATION",
}

def money(v:Decimal)->Decimal:return v.quantize(CENT,rounding=ROUND_HALF_UP)
def digest(v:dict)->str:return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def monthly_rate(track: str, institutional_annual: Decimal = Decimal("14"), retail_monthly: Decimal = Decimal("2.5")) -> Decimal:
    _ = track, institutional_annual
    return retail_monthly / HUNDRED

def price_schedule(principal:Decimal,rate:Decimal,ipca:Decimal,balloon:bool=False)->list[dict]:
    calculation_term=60 if balloon else 36
    factor=(Decimal(1)+rate)**calculation_term
    installment=principal*rate*factor/(factor-Decimal(1));balance=principal;rows=[]
    for month in range(1,37):
        if month in {13,25}:installment*=Decimal(1)+ipca/HUNDRED
        opening=balance;interest=opening*rate
        if month==36:payment=opening+interest;amortization=opening;balance=Decimal(0)
        else:payment=installment;amortization=payment-interest;balance=max(Decimal(0),opening-amortization)
        rows.append({"month":month,"opening_balance":str(money(opening)),"installment":str(money(payment)),"interest":str(money(interest)),"principal_amortization":str(money(amortization)),"settlement_balance":str(money(balance)),"ipca_adjusted":month in {13,25}})
    return rows

def pool_public_simulation(asset_value:Decimal,requested_amount:Decimal|None,retail_monthly:Decimal=Decimal("2.5"))->dict:
    limit=money(asset_value*Decimal("0.40"));principal=money(requested_amount or limit)
    if principal>limit:raise HTTPException(422,f"LTV máximo de 40% excedido; limite {limit}")
    platform_fee_percent=Decimal("10");itbi_percent=Decimal("3")
    platform_fee=money(principal*platform_fee_percent/HUNDRED)
    itbi_provision=money(principal*itbi_percent/HUNDRED)
    net_payout=money(principal-platform_fee-itbi_provision)
    rate=retail_monthly/HUNDRED
    schedule=price_schedule(principal,rate,Decimal("0"),balloon=False)
    monthly_payment=schedule[0]["installment"] if schedule else "0.00"
    return {
        "track":"POOL","asset_value":str(money(asset_value)),"principal":str(principal),
        "ltv_percent":str(money(principal/asset_value*HUNDRED)),"retail_rate_monthly":str(retail_monthly),
        "amortization":"PRICE","platform_fee_percent":str(platform_fee_percent),"platform_fee":str(platform_fee),
        "itbi_percent":str(itbi_percent),"itbi_provision":str(itbi_provision),"net_payout":str(net_payout),
        "partner_commission_base":str(net_payout),"monthly_payment":monthly_payment,"monthly_schedule":schedule,
        "interest_basis":"NOMINAL_PRINCIPAL","execution":"SIMULATION_ONLY",
    }

def pool_public_simulation(
    asset_value: Decimal,
    requested_amount: Decimal | None,
    retail_monthly: Decimal = Decimal("2.5"),
    ipca: Decimal = Decimal("0"),
) -> dict:
    """Simulação pública Flash Capital — somente trilha POOL (2,5% a.m. Price)."""
    _ = ipca
    limit = money(asset_value * Decimal("0.40"))
    principal = money(requested_amount or limit)
    if principal > limit:
        raise HTTPException(422, f"LTV máximo de 40% excedido; limite {limit}")
    platform_fee_percent = Decimal("10")
    itbi_percent = Decimal("3")
    platform_fee = money(principal * platform_fee_percent / HUNDRED)
    itbi_provision = money(principal * itbi_percent / HUNDRED)
    net_payout = money(principal - platform_fee - itbi_provision)
    rate = monthly_rate("POOL", retail_monthly=retail_monthly)
    schedule = price_schedule(principal, rate, Decimal("0"), balloon=False)
    payment = schedule[0]["installment"] if schedule else "0.00"
    return {
        "track": "POOL",
        "asset_value": str(money(asset_value)),
        "principal": str(principal),
        "ltv_percent": str(money(principal / asset_value * HUNDRED)),
        "retail_rate_monthly": str(retail_monthly),
        "rate_basis": "2,5% a.m. Tabela Price (trilha pool)",
        "platform_fee_percent": str(platform_fee_percent),
        "platform_fee": str(platform_fee),
        "itbi_percent": str(itbi_percent),
        "itbi_provision": str(itbi_provision),
        "net_payout": str(net_payout),
        "partner_commission_base": str(net_payout),
        "monthly_payment": payment,
        "monthly_schedule": schedule,
        "interest_basis": "NOMINAL_PRINCIPAL",
        "execution": "SIMULATION_ONLY",
    }


def four_scenarios(asset_value:Decimal,requested_amount:Decimal|None,ipca:Decimal,institutional_annual:Decimal=Decimal("14"),retail_monthly:Decimal=Decimal("2.5"))->dict:
    _ = ipca
    limit=money(asset_value*Decimal("0.40"));principal=money(requested_amount or limit)
    if principal>limit:raise HTTPException(422,f"LTV máximo de 40% excedido; limite {limit}")
    platform_fee_percent=Decimal("10");itbi_percent=Decimal("3")
    platform_fee=money(principal*platform_fee_percent/HUNDRED)
    itbi_provision=money(principal*itbi_percent/HUNDRED)
    net_payout=money(principal-platform_fee-itbi_provision)
    scenarios={}
    rate=monthly_rate("POOL",institutional_annual,retail_monthly)
    for track in ("FUNDS","POOL"):
        for balloon in (False,True):scenarios[f"{track.lower()}_{'balloon' if balloon else 'linear'}"]=price_schedule(principal,rate,Decimal("0"),balloon)
    return {"asset_value":str(money(asset_value)),"principal":str(principal),"ltv_percent":str(money(principal/asset_value*HUNDRED)),"coverage_factor":"2.5x","ipca_projected_percent":str(ipca),"institutional_rate_annual":str(institutional_annual),"retail_rate_monthly":str(retail_monthly),"rate_basis_funds":"2,5% a.m. Tabela Price (fruição fixa)","rate_basis_pool":"2,5% a.m. Tabela Price (fruição fixa)","platform_fee_percent":str(platform_fee_percent),"platform_fee":str(platform_fee),"itbi_percent":str(itbi_percent),"itbi_provision":str(itbi_provision),"net_payout":str(net_payout),"partner_commission_base":str(net_payout),"interest_basis":"NOMINAL_PRINCIPAL","execution":"SIMULATION_ONLY","scenarios":scenarios}

def settlement_curve(principal:Decimal,track:str,ipca:Decimal,balloon:bool,institutional_annual:Decimal=Decimal("14"),retail_monthly:Decimal=Decimal("2.5"))->dict:
    _ = ipca
    rows=price_schedule(principal,monthly_rate(track,institutional_annual,retail_monthly),Decimal("0"),balloon)
    return {"principal":str(money(principal)),"track":track,"balloon":balloon,"institutional_rate_annual":str(institutional_annual),"retail_rate_monthly":str(retail_monthly),"execution":"SIMULATION_ONLY","curve":[{"installment":r["month"],"settlement_amount":r["opening_balance"]} for r in rows if r["month"]>=6]}

def sdc_bullet_and_split(capital:Decimal,turnover_days:int,commission_pool:Decimal,level3_available:bool)->dict:
    if turnover_days not in {45,90}:raise HTTPException(422,"Prazo SDC deve ser 45 ou 90 dias")
    interest=money(capital*Decimal("0.025")*Decimal(turnover_days)/Decimal(30));total=money(capital+interest)
    master=money(commission_pool*Decimal("0.50"));remainder=commission_pool-master
    weights={"direct_seller":Decimal(35),"upline_level_1":Decimal(7),"upline_level_2":Decimal(5),"upline_level_3":Decimal(3)}
    split={key:money(remainder*weight/Decimal(50)) for key,weight in weights.items()}
    if not level3_available:split["holding_residual"]=split.pop("upline_level_3")
    return {"capital":str(money(capital)),"turnover_days":turnover_days,"simple_interest_rate_percent":str(money(Decimal("2.5")*Decimal(turnover_days)/Decimal(30))),"bullet_interest":str(interest),"investor_total":str(total),"commission_pool":str(money(commission_pool)),"split":{"master_franchisee":str(master),**{k:str(v) for k,v in split.items()}},"split_basis":"MASTER_50_PERCENT_PLUS_REMAINDER_NORMALIZED_35_7_5_3","fiscal_status":"PENDING_FISCAL","execution":"PREVIEW_ONLY_NO_FUNDS"}

def create_contract_quote(db:Session,user:User,contract:Contract,principal:Decimal,track:str,ipca:Decimal,balloon:bool,current_installment:int,institutional_annual:Decimal=Decimal("14"),retail_monthly:Decimal=Decimal("2.5"))->EarlySettlementQuote:
    _ = ipca
    if not 1<=current_installment<=36:raise HTTPException(422,"Parcela corrente deve estar entre 1 e 36")
    rows=price_schedule(principal,monthly_rate(track,institutional_annual,retail_monthly),Decimal("0"),balloon);amount=Decimal(rows[current_installment-1]["opening_balance"])
    remaining=sum((Decimal(r["installment"]) for r in rows[current_installment-1:]),Decimal(0));discount=max(Decimal(0),remaining-amount)
    evidence={"contract_id":contract.id,"installment":current_installment,"track":track,"balloon":balloon,"principal":str(money(principal)),"amount":str(money(amount)),"ipca":str(ipca)}
    item=EarlySettlementQuote(organization_id=user.organization_id,contract_id=contract.id,requested_by_id=user.id,installment_number=current_installment,track=track,balloon=balloon,principal=principal,settlement_amount=amount,future_interest_discount=discount,calculation_hash=digest(evidence),expires_at=datetime.now(UTC)+timedelta(minutes=60))
    db.add(item);db.flush();return item

def ingest_event(db:Session,user:User,event_id:str,event_type:str,aggregate_id:str,payload:dict)->tuple[FinOpsDomainEvent,bool]:
    existing=db.scalar(select(FinOpsDomainEvent).where(FinOpsDomainEvent.organization_id==user.organization_id,FinOpsDomainEvent.event_id==event_id))
    if existing:
        if existing.payload_hash!=digest(payload):raise HTTPException(409,"Event ID reutilizado com payload diferente")
        return existing,False
    if event_type not in SUPPORTED_EVENTS:raise HTTPException(422,"Evento FinOps não suportado")
    item=FinOpsDomainEvent(organization_id=user.organization_id,event_id=event_id,event_type=event_type,aggregate_id=aggregate_id,payload_json=json.dumps(payload,ensure_ascii=False,sort_keys=True),payload_hash=digest(payload),decision=SUPPORTED_EVENTS[event_type])
    db.add(item);db.flush();return item,True
