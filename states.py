from aiogram.fsm.state import State, StatesGroup


class UserRegistration(StatesGroup):
    age             = State()
    pseudonym       = State()
    characteristics = State()
    hobbies         = State()


class EditProfile(StatesGroup):
    choosing_field = State()
    entering_value = State()


class CreateDialog(StatesGroup):
    choose_mode  = State()
    choose_admin = State()


class ActiveDialog(StatesGroup):
    chatting = State()   # both user AND admin reuse this state


class CreateReview(StatesGroup):
    choose_admin   = State()
    choose_dialog  = State()
    enter_text     = State()
    choose_rating  = State()
    attach_media   = State()


class CreateChannelPost(StatesGroup):
    enter_content = State()
    attach_media  = State()


class AdminFillProfile(StatesGroup):
    age             = State()
    characteristics = State()
    hobbies         = State()
    description     = State()


class AdminEditChannel(StatesGroup):
    choosing_field = State()
    entering_value = State()


class SuperAdminAddAdmin(StatesGroup):
    telegram_id = State()
    username    = State()
    pseudonym   = State()
    confirm     = State()


class SuperAdminBan(StatesGroup):
    user_id = State()
    reason  = State()


class SuperAdminUnban(StatesGroup):
    user_id = State()


class SuperAdminWarn(StatesGroup):
    user_id = State()


class SuperAdminBroadcast(StatesGroup):
    content = State()
    media   = State()
    confirm = State()
