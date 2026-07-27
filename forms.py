"""
Formulaires WTForms pour l'application Topili
"""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, FloatField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, NumberRange, Regexp
from flask_login import current_user
from models import User

class LoginForm(FlaskForm):
    """Formulaire de connexion"""
    username = StringField('Nom d\'utilisateur', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Mot de passe', validators=[DataRequired()])
    submit = SubmitField('Connexion')

class RegisterForm(FlaskForm):
    """Formulaire d'inscription"""
    username = StringField('Nom d\'utilisateur', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Mot de passe', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirmer le mot de passe',
                                    validators=[DataRequired(), EqualTo('password')])
    phone = StringField('Numéro de téléphone', validators=[Length(min=0, max=20)])
    submit = SubmitField('S\'inscrire')
    
    def validate_username(self, username):
        """Vérifier que l'username n'existe pas"""
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Ce nom d\'utilisateur est déjà pris.')
    
    def validate_email(self, email):
        """Vérifier que l'email n'existe pas"""
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Cet email est déjà enregistré.')

class TransferCreditForm(FlaskForm):
    """Formulaire de transfert de crédit"""
    client_id = SelectField('Client destinataire', coerce=int, validators=[DataRequired()])
    operator = SelectField('Opérateur', choices=[('djezzy', 'Djezzy'), ('ooredoo', 'Ooredoo'), ('mobilis', 'Mobilis')], validators=[DataRequired()])
    amount = FloatField('Montant (DA)', validators=[
        DataRequired(),
        NumberRange(min=0.01, message='Le montant doit être positif')
    ])
    description = TextAreaField('Description (optionnel)', validators=[Length(min=0, max=255)])
    submit = SubmitField('Envoyer le crédit')

class SendCreditByPhoneForm(FlaskForm):
    """Formulaire d'envoi de crédit vers un numéro de téléphone"""
    phone_number = StringField('Numéro de téléphone destinataire', validators=[
        DataRequired(),
        Regexp(r'^0[567]\d{8}$', message='Numéro invalide (ex: 0661234567)')
    ])
    amount = FloatField('Montant (DA)', validators=[
        DataRequired(),
        NumberRange(min=1, message='Le montant doit être au moins 1 DA')
    ])
    submit = SubmitField('Envoyer le crédit')


class AddClientForm(FlaskForm):
    """Formulaire pour ajouter un client"""
    username = StringField('Nom d\'utilisateur', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Numéro de téléphone', validators=[Length(min=0, max=20)])
    operator = SelectField('Opérateur', choices=[('djezzy', 'Djezzy'), ('ooredoo', 'Ooredoo'), ('mobilis', 'Mobilis')], validators=[DataRequired()])
    amount = FloatField('Solde initial (DA)', validators=[
        DataRequired(),
        NumberRange(min=0, message='Le solde doit être positif ou zéro')
    ])
    submit = SubmitField('Ajouter le client')
    
    def validate_username(self, username):
        """Vérifier que l'username n'existe pas"""
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Ce nom d\'utilisateur est déjà pris.')
    
    def validate_email(self, email):
        """Vérifier que l'email n'existe pas"""
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Cet email est déjà enregistré.')

class ProfileUpdateForm(FlaskForm):
    """Formulaire de mise à jour du profil"""
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Numéro de téléphone', validators=[Length(min=0, max=20)])
    submit = SubmitField('Mettre à jour')

class ChangePasswordForm(FlaskForm):
    """Formulaire de changement de mot de passe"""
    old_password = PasswordField('Ancien mot de passe', validators=[DataRequired()])
    new_password = PasswordField('Nouveau mot de passe', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirmer le nouveau mot de passe',
                                    validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Changer le mot de passe')


# ==================== Formulaires Admin ====================

class AdjustUserBalanceForm(FlaskForm):
    """Formulaire pour ajuster le solde d'un utilisateur"""
    user_id = SelectField('Utilisateur', coerce=int, validators=[DataRequired()])
    operator = SelectField('Opérateur', choices=[('djezzy', 'Djezzy'), ('ooredoo', 'Ooredoo'), ('mobilis', 'Mobilis')], validators=[DataRequired()])
    amount = FloatField('Montant', validators=[DataRequired(), NumberRange(min=-999999, max=999999)])
    reason = TextAreaField('Raison de l\'ajustement', validators=[DataRequired(), Length(min=10, max=500)])
    submit = SubmitField('Confirmer l\'ajustement')


class AddOperatorForm(FlaskForm):
    """Formulaire pour ajouter un opérateur"""
    name = StringField('Nom de l\'opérateur', validators=[DataRequired(), Length(min=3, max=50)])
    code = StringField('Code court', validators=[DataRequired(), Length(min=2, max=10)])
    description = TextAreaField('Description', validators=[Length(min=0, max=255)])
    submit = SubmitField('Ajouter opérateur')


class SystemSettingForm(FlaskForm):
    """Formulaire pour les paramètres système"""
    commission_rate = FloatField('Taux de commission (%)', validators=[NumberRange(min=0, max=100)])
    max_transaction = FloatField('Montant max transaction', validators=[NumberRange(min=0)])
    min_transaction = FloatField('Montant min transaction', validators=[NumberRange(min=0)])
    submit = SubmitField('Sauvegarder les paramètres')


class CreateAdminForm(FlaskForm):
    """Formulaire pour créer un compte admin"""
    username = StringField('Nom d\'utilisateur', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Mot de passe', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirmer', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Créer admin')
