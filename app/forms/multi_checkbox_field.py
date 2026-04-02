from wtforms import SelectMultipleField
from wtforms.widgets import ListWidget, CheckboxInput

class MultiCheckboxField(SelectMultipleField):
    """A multiple-select, displayed as a list of checkboxes."""

    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

