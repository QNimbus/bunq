# generated by datamodel-codegen:
#   filename:  callback.schema.json
#   timestamp: 2023-11-21T19:58:07+00:00

from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional, Union

from pydantic import BaseModel, RootModel, constr


class GeolocationType(RootModel[Any]):
    root: Any


class AmountType(BaseModel):
    currency: str
    value: str


class AttachmentType(RootModel[Optional[List[str]]]):
    root: Optional[List[str]]


class DateTimeType(
    RootModel[constr(pattern=r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{1,6}$')]
):
    root: constr(pattern=r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{1,6}$')


class DecisionType(Enum):
    ALLOWED = 'ALLOWED'
    PIN_INCORRECT = 'PIN_INCORRECT'


class CategoryType(Enum):
    MUTATION = 'MUTATION'
    REQUEST = 'REQUEST'
    SCHEDULE_RESULT = 'SCHEDULE_RESULT'
    SCHEDULE_STATUS = 'SCHEDULE_STATUS'
    PAYMENT = 'PAYMENT'
    DRAFT_PAYMENT = 'DRAFT_PAYMENT'
    BILLING = 'BILLING'
    IDEAL = 'IDEAL'
    SOFORT = 'SOFORT'
    CARD_TRANSACTION_FAILED = 'CARD_TRANSACTION_FAILED'
    CARD_TRANSACTION_SUCCESSFUL = 'CARD_TRANSACTION_SUCCESSFUL'


class EventType(Enum):
    MUTATION_CREATED = 'MUTATION_CREATED'
    MUTATION_RECEIVED = 'MUTATION_RECEIVED'
    PAYMENT_CREATED = 'PAYMENT_CREATED'
    PAYMENT_RECEIVED = 'PAYMENT_RECEIVED'
    CARD_PAYMENT_ALLOWED = 'CARD_PAYMENT_ALLOWED'
    CARD_TRANSACTION_NOT_ALLOWED = 'CARD_TRANSACTION_NOT_ALLOWED'
    REQUEST_INQUIRY_CREATED = 'REQUEST_INQUIRY_CREATED'
    REQUEST_INQUIRY_ACCEPTED = 'REQUEST_INQUIRY_ACCEPTED'
    REQUEST_INQUIRY_REJECTED = 'REQUEST_INQUIRY_REJECTED'
    REQUEST_RESPONSE_CREATED = 'REQUEST_RESPONSE_CREATED'
    REQUEST_RESPONSE_ACCEPTED = 'REQUEST_RESPONSE_ACCEPTED'
    REQUEST_RESPONSE_REJECTED = 'REQUEST_RESPONSE_REJECTED'


class Url(BaseModel):
    type: str
    url: str


class ImageType1(BaseModel):
    attachment_public_uuid: str
    height: int
    width: int
    content_type: str
    urls: List[Url]


class ImageType(RootModel[List[ImageType1]]):
    root: List[ImageType1]


class AvatarType(BaseModel):
    uuid: str
    image: ImageType
    anchor_uuid: Optional[str] = None
    style: str


class LabelUser(BaseModel):
    uuid: Optional[str] = None
    display_name: str
    country: str
    avatar: Optional[AvatarType] = None
    public_nick_name: str
    type: Optional[str] = None


class LabelCard(BaseModel):
    uuid: Optional[str] = None
    type: Optional[str] = None
    second_line: Optional[str] = None
    expiry_date: str
    status: str
    label_user: LabelUser


class AliasOrCounterpartyAlias(BaseModel):
    iban: Optional[str] = None
    is_light: Optional[bool] = None
    display_name: str
    avatar: Optional[AvatarType] = None
    label_user: LabelUser
    country: str


class PaymentType(BaseModel):
    id: int
    created: DateTimeType
    updated: DateTimeType
    monetary_account_id: int
    amount: AmountType
    description: str
    type: str
    merchant_reference: Optional[str] = None
    alias: AliasOrCounterpartyAlias
    counterparty_alias: AliasOrCounterpartyAlias
    attachment: AttachmentType
    geolocation: GeolocationType
    batch_id: Optional[int] = None
    scheduled_id: Optional[int] = None
    address_billing: Optional[str] = None
    address_shipping: Optional[str] = None
    sub_type: str
    request_reference_split_the_bill: List[str]
    balance_after_mutation: AmountType
    payment_auto_allocate_instance: Optional[str] = None


class RequestInquiryType(BaseModel):
    id: int
    created: DateTimeType
    updated: DateTimeType
    time_responded: Optional[DateTimeType] = None
    time_expiry: Optional[DateTimeType] = None
    monetary_account_id: int
    amount_inquired: AmountType
    amount_responded: Optional[AmountType] = None
    status: str
    description: str
    merchant_reference: Optional[str] = None
    counterparty_alias: AliasOrCounterpartyAlias
    attachment: AttachmentType
    minimum_age: Optional[int] = None
    require_address: Optional[str] = None
    geolocation: GeolocationType
    bunqme_share_url: Optional[str] = None
    redirect_url: Optional[str] = None
    reference_split_the_bill: Optional[str] = None
    batch_id: Optional[int] = None
    scheduled_id: Optional[int] = None
    address_billing: Optional[str] = None
    address_shipping: Optional[str] = None


class RequestResponseType(BaseModel):
    id: int
    created: DateTimeType
    updated: DateTimeType
    time_responded: Optional[DateTimeType] = None
    time_expiry: Optional[DateTimeType] = None
    monetary_account_id: int
    amount_inquired: AmountType
    amount_responded: Optional[AmountType] = None
    status: str
    description: str
    alias: AliasOrCounterpartyAlias
    counterparty_alias: AliasOrCounterpartyAlias
    attachment: AttachmentType
    minimum_age: Optional[int] = None
    require_address: Optional[str] = None
    geolocation: GeolocationType
    type: str
    sub_type: str
    redirect_url: Optional[str] = None
    address_billing: Optional[str] = None
    address_shipping: Optional[str] = None
    eligible_whitelist_id: Optional[int] = None
    request_reference_split_the_bill: List
    event_id: Optional[int] = None
    monetary_account_preferred_id: Optional[int] = None


class MasterCardActionType(BaseModel):
    id: int
    created: DateTimeType
    updated: DateTimeType
    monetary_account_id: int
    card_id: Optional[int] = None
    card_authorisation_id_response: Optional[str] = None
    amount_local: Optional[AmountType] = None
    amount_converted: Optional[AmountType] = None
    amount_billing: Optional[AmountType] = None
    amount_original_local: Optional[AmountType] = None
    amount_original_billing: Optional[AmountType] = None
    amount_fee: Optional[AmountType] = None
    decision: Optional[DecisionType] = None
    payment_status: Optional[str] = None
    decision_description: Optional[str] = None
    decision_description_translated: Optional[str] = None
    decision_together_url: Optional[str] = None
    description: Optional[str] = None
    authorisation_status: Optional[str] = None
    authorisation_type: Optional[str] = None
    settlement_status: Optional[str] = None
    clearing_status: Optional[str] = None
    maturity_date: Optional[str] = None
    city: Optional[str] = None
    alias: Optional[AliasOrCounterpartyAlias] = None
    counterparty_alias: Optional[AliasOrCounterpartyAlias] = None
    label_card: Optional[LabelCard] = None
    merchant_id: Optional[str] = None
    token_status: Optional[str] = None
    reservation_expiry_time: Optional[str] = None
    clearing_expiry_time: Optional[DateTimeType] = None
    pan_entry_mode_user: Optional[str] = None
    secure_code_id: Optional[str] = None
    wallet_provider_id: Optional[str] = None
    request_reference_split_the_bill: Optional[List] = None
    applied_limit: Optional[str] = None
    pos_card_presence: Optional[str] = None
    pos_card_holder_presence: Optional[str] = None
    eligible_whitelist_id: Optional[int] = None
    cashback_payout_item: Optional[str] = None
    mastercard_action_report: Optional[str] = None
    blacklist: Optional[str] = None
    additional_authentication_status: Optional[str] = None
    pin_status: Optional[str] = None


class Payment(BaseModel):
    Payment: PaymentType


class RequestInquiry(BaseModel):
    RequestInquiry: RequestInquiryType


class RequestResponseTypeModel(BaseModel):
    RequestResponse: RequestResponseType


class MasterCardAction(BaseModel):
    MasterCardAction: MasterCardActionType


class ObjectType(
    RootModel[
        Union[Payment, RequestInquiry, RequestResponseTypeModel, MasterCardAction]
    ]
):
    root: Union[Payment, RequestInquiry, RequestResponseTypeModel, MasterCardAction]


class NotificationUrl(BaseModel):
    target_url: str
    category: CategoryType
    event_type: EventType
    object: ObjectType


class CallbackModel(BaseModel):
    NotificationUrl: NotificationUrl
