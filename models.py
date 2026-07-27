"""
Modèles de données pour l'application Topili
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """Modèle utilisateur (Point de Vente et Clients)"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20))
    
    # Type de rôle: 'pdv' (Point de Vente/Admin) ou 'client'
    role = db.Column(db.String(20), default='client', nullable=False)
    
    # Pour les clients : référence au Point de Vente
    pdv_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Solde de crédit par opérateur
    balance_djezzy = db.Column(db.Float, default=0.0, nullable=False)
    balance_ooredoo = db.Column(db.Float, default=0.0, nullable=False)
    balance_mobilis = db.Column(db.Float, default=0.0, nullable=False)
    
    # Statut du compte
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Dates
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relations
    clients = db.relationship('User', backref=db.backref('pdv', remote_side=[id]), 
                             foreign_keys=[pdv_id])
    sent_transactions = db.relationship('Transaction', foreign_keys='Transaction.sender_id',
                                       backref='sender', lazy=True)
    received_transactions = db.relationship('Transaction', foreign_keys='Transaction.receiver_id',
                                           backref='receiver', lazy=True)
    
    def set_password(self, password):
        """Hasher le mot de passe"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Vérifier le mot de passe"""
        return check_password_hash(self.password_hash, password)
    
    def get_total_balance(self):
        """Retourner le solde total de tous les opérateurs"""
        return self.balance_djezzy + self.balance_ooredoo + self.balance_mobilis
    
    def get_balance_by_operator(self, operator):
        """Obtenir le solde pour un opérateur spécifique"""
        if operator == 'djezzy':
            return self.balance_djezzy
        elif operator == 'ooredoo':
            return self.balance_ooredoo
        elif operator == 'mobilis':
            return self.balance_mobilis
        return 0.0
    
    def add_balance(self, amount, operator='djezzy'):
        """Ajouter au solde d'un opérateur"""
        if operator == 'djezzy':
            self.balance_djezzy += amount
        elif operator == 'ooredoo':
            self.balance_ooredoo += amount
        elif operator == 'mobilis':
            self.balance_mobilis += amount
        self.updated_at = datetime.now(timezone.utc)
    
    def subtract_balance(self, amount, operator='djezzy'):
        """Soustraire du solde de façon atomique (protège contre les écritures simultanées)"""
        column = getattr(User, f'balance_{operator}', None)
        if column is None:
            return False
        updated = db.session.query(User).filter(
            User.id == self.id,
            column >= amount
        ).update(
            {column: column - amount, "updated_at": datetime.now(timezone.utc)},
            synchronize_session="fetch"
        )
        return updated > 0
    
    def __repr__(self):
        return f'<User {self.username}>'


class Transaction(db.Model):
    """Modèle de transaction de crédit"""
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Opérateur utilisé
    operator = db.Column(db.String(20), default='djezzy', nullable=False)
    
    # Montant en DA (Dinar Algérien)
    amount = db.Column(db.Float, nullable=False)

    # Numéro de téléphone destinataire (pour les envois de crédit vers l'extérieur)
    recipient_phone = db.Column(db.String(20), nullable=True)

    # Description/Raison de la transaction
    description = db.Column(db.String(255))

    # Statut: 'completed', 'pending', 'failed'
    status = db.Column(db.String(20), default='completed', nullable=False)
    
    # Date de création
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    def __repr__(self):
        return f'<Transaction {self.id}: {self.sender_id} -> {self.receiver_id} : {self.amount}>'


class Operator(db.Model):
    """Modèle pour les opérateurs télécom"""
    __tablename__ = 'operators'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False)
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<Operator {self.name}>'


class AuditLog(db.Model):
    """Modèle pour les logs d'audit"""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    status = db.Column(db.String(20), default='success')  # success, error
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    user = db.relationship('User', backref='audit_logs')
    
    def __repr__(self):
        return f'<AuditLog {self.id}: {self.action}>'


class SystemSetting(db.Model):
    """Modèle pour les paramètres système"""
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    setting_type = db.Column(db.String(20), default='string')  # string, number, boolean
    description = db.Column(db.String(255))
    
    def __repr__(self):
        return f'<SystemSetting {self.key}>'


class PdVCommission(db.Model):
    """Modèle pour tracker les commissions des PdV"""
    __tablename__ = 'pdv_commissions'
    
    id = db.Column(db.Integer, primary_key=True)
    pdv_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    rate = db.Column(db.Float, default=2.0)  # Pourcentage
    paid = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    pdv = db.relationship('User', backref='commissions')
    transaction = db.relationship('Transaction', backref='commission')
    
    def __repr__(self):
        return f'<PdVCommission {self.id}: {self.amount}>'
