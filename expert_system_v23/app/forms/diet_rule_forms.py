from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectMultipleField, widgets, BooleanField
from wtforms.validators import DataRequired, Length, Optional
from app.models.goal import GoalsTable

class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()

class DietRuleForm(FlaskForm):
    rule_name = StringField('Rule Name', 
                           validators=[DataRequired(), Length(min=3, max=120)],
                           render_kw={"placeholder": "e.g., Low Sodium Diet for Hypertension"})
    
    description = TextAreaField('Description', 
                               validators=[DataRequired(), Length(max=255)],
                               render_kw={"rows": 3, "placeholder": "Describe the diet rule and its purpose..."})
    
    conditions = TextAreaField('Conditions & Rules', 
                              validators=[Optional()],
                              render_kw={"rows": 5, "placeholder": "Enter specific conditions, restrictions, or guidelines..."})
    
    # Multi-select fields for goals
    goals = MultiCheckboxField('Health Goals', 
                              coerce=int,
                              choices=[])
    
    active = BooleanField('Active', default=True)
    
    def __init__(self, *args, **kwargs):
        super(DietRuleForm, self).__init__(*args, **kwargs)
        # Populate choices dynamically
        self.goals.choices = [(g.id, g.name) for g in GoalsTable.query.all()]
