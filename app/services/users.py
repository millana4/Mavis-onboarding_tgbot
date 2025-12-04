from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
from datetime import date, datetime


class UserRole(str, Enum):
    EMPLOYEE = "employee"
    NEWCOMER = "newcomer"


class User(BaseModel):
    # Обязательные поля
    id: str = Field(..., description="Уникальный идентификатор - СНИЛС")
    surname: str = Field(..., min_length=1, description="Фамилия")
    name: str = Field(..., min_length=1, description="Имя")
    role: UserRole = Field(default=UserRole.EMPLOYEE, description="Роль в системе")

    # Необязательные поля
    patronymic: Optional[str] = Field(None, description="Отчество")
    maiden: Optional[str] = Field(None, description="Девичья фамилия")
    maiden1: Optional[str] = Field(None, description="Девичья фамилия1")
    maiden2: Optional[str] = Field(None, description="Девичья фамилия2")
    date_start_working: Optional[date] = Field(None, description="Дата оформления на работу из 1С")

    companies: Optional[str] = Field(None, description="Список компаний, в которые трудоустроен")
    main_company: str = Field(None, description="Основная компания")
    department: Optional[str] = Field(None, description="Отдел")
    position: Optional[str] = Field(None, description="Должность")

    phone: List[str] = Field(default_factory=list, description="Личный телефон")
    phone1: List[str] = Field(default_factory=list, description="Дополнительный личный телефон")
    phone2: List[str] = Field(default_factory=list, description="Второй дополнительный личный телефон")
    phone_corp: List[str] = Field(default_factory=list, description="Корпоративный номер телефона")
    phone_suffix: List[str] = Field(default_factory=list, description="Добавочный номер")

    email: Optional[str] = Field(None, description="Основной email, указанный в 1С")
    email_mavis: Optional[str] = Field(None, description="Email Мависа")
    email_votonia: Optional[str] = Field(None, description="Email Вотони")

    photo: Optional[str] = Field(None, description="Ссылка на фото")

    id_messenger: Optional[str] = Field(None, description="ID в мессенджере")
    date_registr: Optional[datetime] = Field(None, description="Дата регистрации в боте")
    group: List[str] = Field(default_factory=list, description="Группы рассылки уведомлений")
    admin: bool = Field(False, description="Является ли администратором")



    # Написать скрипт для удаления: периодически обходить выгрузку 1С и удалять пользователя из таблицы с доступом, идентифицировать в Снилсу


