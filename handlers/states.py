from aiogram.fsm.state import State, StatesGroup

class Form(StatesGroup):
    project_name = State()
    project_limit = State()
    folder_name = State()
    component_name = State()
    component_mass = State()
    component_qty = State()
    note_text = State()
    waiting_file = State()
    file_mass = State()
    file_comment = State()
    file_qty = State()
    component_waiting_file = State()
    component_file_comment = State()
