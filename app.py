"""
Application Flask principale pour Topili
"""
import os
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
from functools import wraps

from config import config
from models import db, User, Transaction, Operator, AuditLog, SystemSetting, PdVCommission
from forms import (LoginForm, RegisterForm, TransferCreditForm, 
                   AddClientForm, ProfileUpdateForm, ChangePasswordForm,
                   AdjustUserBalanceForm, AddOperatorForm, SystemSettingForm, CreateAdminForm)

# Configuration Flask
app = Flask(__name__)
app.config.from_object(config['development'])

# Initialisation des extensions
db.init_app(app)

# Configuration Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Décorateur pour vérifier le rôle
def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != role:
                flash('Vous n\'avez pas accès à cette page.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Décorateur pour vérifier les rôles multiples
def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                flash('Vous n\'avez pas accès à cette page.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Fonction pour tracker les actions d'audit
def log_audit(action, description='', status='success'):
    """Enregistrer une action d'audit"""
    try:
        audit = AuditLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            description=description,
            ip_address=request.remote_addr,
            status=status
        )
        db.session.add(audit)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Erreur audit: {e}")

# Fonction pour obtenir les settings
def get_setting(key, default=None):
    """Obtenir une valeur de setting"""
    setting = SystemSetting.query.filter_by(key=key).first()
    if setting:
        if setting.setting_type == 'number':
            return float(setting.value)
        elif setting.setting_type == 'boolean':
            return setting.value.lower() == 'true'
        return setting.value
    return default

# Fonction pour définir les settings
def set_setting(key, value, setting_type='string', description=''):
    """Définir une valeur de setting"""
    setting = SystemSetting.query.filter_by(key=key).first()
    if setting:
        setting.value = str(value)
    else:
        setting = SystemSetting(key=key, value=str(value), setting_type=setting_type, description=description)
        db.session.add(setting)
    db.session.commit()

# ==================== Routes d'authentification ====================

@app.route('/')
def index():
    """Page d'accueil"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Page de connexion"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user is None or not user.check_password(form.password.data):
            flash('Nom d\'utilisateur ou mot de passe incorrect.', 'danger')
            return redirect(url_for('login'))
        
        if not user.is_active:
            flash('Votre compte a été désactivé.', 'danger')
            return redirect(url_for('login'))
        
        login_user(user)
        next_page = request.args.get('next')
        return redirect(next_page) if next_page else redirect(url_for('dashboard'))
    
    return render_template('auth/login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Page d'enregistrement (pour les clients)"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            phone=form.phone.data,
            role='client'
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        flash('Inscription réussie! Veuillez vous connecter.', 'success')
        return redirect(url_for('login'))
    
    return render_template('auth/register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    """Déconnexion"""
    logout_user()
    flash('Vous avez été déconnecté.', 'info')
    return redirect(url_for('login'))

# ==================== Routes du tableau de bord ====================

@app.route('/dashboard')
@login_required
def dashboard():
    """Tableau de bord principal"""
    if current_user.role == 'pdv':
        # Pour le Point de Vente
        total_clients = User.query.filter_by(pdv_id=current_user.id, role='client').count()
        total_balance_distributed = db.session.query(db.func.sum(User.balance)).filter(
            User.pdv_id == current_user.id,
            User.role == 'client'
        ).scalar() or 0
        
        # Transactions récentes
        recent_transactions = Transaction.query.filter(
            db.or_(
                Transaction.sender_id == current_user.id,
                Transaction.receiver_id == current_user.id
            )
        ).order_by(Transaction.created_at.desc()).limit(10).all()
        
        return render_template('pdv/dashboard.html',
                             total_clients=total_clients,
                             total_balance_distributed=total_balance_distributed,
                             recent_transactions=recent_transactions)
    else:
        # Pour le Client
        sent_amount = db.session.query(db.func.sum(Transaction.amount)).filter(
            Transaction.sender_id == current_user.id
        ).scalar() or 0
        
        received_amount = db.session.query(db.func.sum(Transaction.amount)).filter(
            Transaction.receiver_id == current_user.id
        ).scalar() or 0
        
        recent_transactions = Transaction.query.filter(
            db.or_(
                Transaction.sender_id == current_user.id,
                Transaction.receiver_id == current_user.id
            )
        ).order_by(Transaction.created_at.desc()).limit(10).all()
        
        return render_template('client/dashboard.html',
                             sent_amount=sent_amount,
                             received_amount=received_amount,
                             recent_transactions=recent_transactions)

# ==================== Routes pour Point de Vente ====================

@app.route('/pdv/clients')
@login_required
@role_required('pdv')
def manage_clients():
    """Gestion des clients pour le PdV"""
    page = request.args.get('page', 1, type=int)
    clients = User.query.filter_by(pdv_id=current_user.id, role='client').paginate(page=page, per_page=20)
    return render_template('pdv/clients.html', clients=clients)

@app.route('/pdv/add-client', methods=['GET', 'POST'])
@login_required
@role_required('pdv')
def add_client():
    """Ajouter un client"""
    form = AddClientForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            phone=form.phone.data,
            role='client',
            pdv_id=current_user.id,
            balance=form.initial_balance.data
        )
        user.set_password('temp123456')  # Mot de passe temporaire
        
        # Soustraire du solde du PdV
        if current_user.subtract_balance(form.initial_balance.data):
            db.session.add(user)
            
            # Créer une transaction
            transaction = Transaction(
                sender_id=current_user.id,
                receiver_id=user.id,
                amount=form.initial_balance.data,
                description='Création du compte client',
                status='completed'
            )
            db.session.add(transaction)
            db.session.commit()
            
            flash(f'Client {user.username} créé avec succès! Mot de passe temporaire: temp123456', 'success')
            return redirect(url_for('manage_clients'))
        else:
            flash('Solde insuffisant pour créer ce client.', 'danger')
    
    return render_template('pdv/add_client.html', form=form)

@app.route('/pdv/transfer', methods=['GET', 'POST'])
@login_required
@role_required('pdv')
def transfer_credit():
    """Transférer du crédit à un client"""
    form = TransferCreditForm()
    
    # Récupérer les clients du PdV
    form.client_id.choices = [(c.id, f"{c.username} (Solde: {c.balance:.2f} DA)")
                               for c in User.query.filter_by(pdv_id=current_user.id, role='client').all()]
    
    if form.validate_on_submit():
        client = User.query.get(form.client_id.data)
        
        if not client or client.pdv_id != current_user.id:
            flash('Client invalide.', 'danger')
            return redirect(url_for('transfer_credit'))
        
        if current_user.subtract_balance(form.amount.data):
            client.add_balance(form.amount.data)
            
            transaction = Transaction(
                sender_id=current_user.id,
                receiver_id=client.id,
                amount=form.amount.data,
                description=form.description.data or 'Transfert de crédit',
                status='completed'
            )
            
            db.session.add(transaction)
            db.session.commit()
            
            flash(f'Transfert de {form.amount.data:.2f} DA vers {client.username} réussi!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Solde insuffisant pour effectuer ce transfert.', 'danger')
    
    return render_template('pdv/transfer.html', form=form)

# ==================== Routes pour Clients ====================

@app.route('/client/send-credit', methods=['GET', 'POST'])
@login_required
@role_required('client')
def send_credit():
    """Envoyer du crédit à un particulier"""
    # Pour le moment, on considère qu'un client ne peut envoyer qu'à d'autres clients
    # du même PdV (les particuliers n'ont pas de compte)
    
    page = request.args.get('page', 1, type=int)
    
    if request.method == 'POST':
        receiver_id = request.form.get('receiver_id', type=int)
        amount = request.form.get('amount', type=float)
        description = request.form.get('description', '')
        
        receiver = User.query.get(receiver_id)
        
        if not receiver or receiver.pdv_id != current_user.pdv_id:
            flash('Destinataire invalide.', 'danger')
            return redirect(url_for('send_credit'))
        
        if receiver.id == current_user.id:
            flash('Vous ne pouvez pas envoyer du crédit à vous-même.', 'danger')
            return redirect(url_for('send_credit'))
        
        if current_user.subtract_balance(amount):
            receiver.add_balance(amount)
            
            transaction = Transaction(
                sender_id=current_user.id,
                receiver_id=receiver.id,
                amount=amount,
                description=description or 'Transfert de crédit',
                status='completed'
            )
            
            db.session.add(transaction)
            db.session.commit()
            
            flash(f'Transfert de {amount:.2f} DA vers {receiver.username} réussi!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Solde insuffisant.', 'danger')
    
    # Récupérer les autres clients du même PdV
    other_clients = User.query.filter(
        User.pdv_id == current_user.pdv_id,
        User.role == 'client',
        User.id != current_user.id
    ).paginate(page=page, per_page=20)
    
    return render_template('client/send_credit.html', other_clients=other_clients)

# ==================== Routes de transactions ====================

@app.route('/transactions')
@login_required
def transactions():
    """Voir l'historique des transactions"""
    page = request.args.get('page', 1, type=int)
    
    transactions_query = Transaction.query.filter(
        db.or_(
            Transaction.sender_id == current_user.id,
            Transaction.receiver_id == current_user.id
        )
    ).order_by(Transaction.created_at.desc())
    
    transactions_paginated = transactions_query.paginate(page=page, per_page=20)
    
    return render_template('transactions.html', transactions=transactions_paginated)

# ==================== Routes de profil ====================

@app.route('/profile')
@login_required
def profile():
    """Page de profil"""
    return render_template('profile.html', user=current_user)

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Éditer le profil"""
    form = ProfileUpdateForm()
    if form.validate_on_submit():
        # Vérifier que l'email n'existe pas (sauf s'il est le même que l'utilisateur courant)
        if form.email.data != current_user.email:
            user = User.query.filter_by(email=form.email.data).first()
            if user:
                flash('Cet email est déjà enregistré.', 'danger')
                return redirect(url_for('edit_profile'))
        
        current_user.email = form.email.data
        current_user.phone = form.phone.data
        db.session.commit()
        flash('Profil mis à jour avec succès!', 'success')
        return redirect(url_for('profile'))
    elif request.method == 'GET':
        form.email.data = current_user.email
        form.phone.data = current_user.phone
    
    return render_template('edit_profile.html', form=form)

@app.route('/profile/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Changer le mot de passe"""
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.old_password.data):
            flash('Ancien mot de passe incorrect.', 'danger')
        else:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash('Mot de passe changé avec succès!', 'success')
            return redirect(url_for('profile'))
    
    return render_template('change_password.html', form=form)

# ==================== Routes Admin ====================

@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    """Tableau de bord admin"""
    total_users = User.query.count()
    total_pdv = User.query.filter_by(role='pdv').count()
    total_clients = User.query.filter_by(role='client').count()
    
    total_transactions = Transaction.query.count()
    total_volume = db.session.query(db.func.sum(Transaction.amount)).scalar() or 0
    
    # Transactions récentes
    recent_transactions = Transaction.query.order_by(Transaction.created_at.desc()).limit(10).all()
    
    # Top PdV
    top_pdv = db.session.query(
        User.username,
        db.func.count(Transaction.id).label('tx_count'),
        db.func.sum(Transaction.amount).label('total_amount')
    ).join(
        Transaction, User.id == Transaction.sender_id
    ).filter(User.role == 'pdv').group_by(User.id).order_by(
        db.func.sum(Transaction.amount).desc()
    ).limit(5).all()
    
    log_audit('ADMIN_DASHBOARD_VIEW', 'Accès au tableau de bord admin')
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_pdv=total_pdv,
                         total_clients=total_clients,
                         total_transactions=total_transactions,
                         total_volume=total_volume,
                         recent_transactions=recent_transactions,
                         top_pdv=top_pdv)

@app.route('/admin/users')
@login_required
@role_required('admin')
def admin_users():
    """Gestion des utilisateurs"""
    page = request.args.get('page', 1, type=int)
    role_filter = request.args.get('role', '')
    search = request.args.get('search', '')
    
    query = User.query
    if role_filter:
        query = query.filter_by(role=role_filter)
    if search:
        query = query.filter(User.username.contains(search) | User.email.contains(search))
    
    users = query.paginate(page=page, per_page=20)
    log_audit('ADMIN_USERS_VIEW', f'Consultation des utilisateurs')
    
    return render_template('admin/users.html', users=users, role_filter=role_filter, search=search)

@app.route('/admin/users/<int:user_id>')
@login_required
@role_required('admin')
def admin_user_detail(user_id):
    """Détails d'un utilisateur"""
    user = User.query.get_or_404(user_id)
    
    # Transactions
    sent_txs = Transaction.query.filter_by(sender_id=user_id).count()
    received_txs = Transaction.query.filter_by(receiver_id=user_id).count()
    sent_volume = db.session.query(db.func.sum(Transaction.amount)).filter_by(sender_id=user_id).scalar() or 0
    received_volume = db.session.query(db.func.sum(Transaction.amount)).filter_by(receiver_id=user_id).scalar() or 0
    
    recent_transactions = Transaction.query.filter(
        (Transaction.sender_id == user_id) | (Transaction.receiver_id == user_id)
    ).order_by(Transaction.created_at.desc()).limit(20).all()
    
    # Clients si c'est un PdV
    clients = None
    if user.role == 'pdv':
        clients = User.query.filter_by(pdv_id=user_id, role='client').all()
    
    log_audit('ADMIN_USER_VIEW', f'Consultation détails utilisateur: {user.username}')
    
    return render_template('admin/user_detail.html',
                         user=user,
                         sent_txs=sent_txs,
                         received_txs=received_txs,
                         sent_volume=sent_volume,
                         received_volume=received_volume,
                         recent_transactions=recent_transactions,
                         clients=clients)

@app.route('/admin/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@role_required('admin')
def admin_toggle_user_status(user_id):
    """Activer/Désactiver un utilisateur"""
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    
    status = 'activé' if user.is_active else 'désactivé'
    log_audit('ADMIN_USER_STATUS_TOGGLE', f'Utilisateur {user.username} {status}')
    
    flash(f'Utilisateur {user.username} {status}!', 'success')
    return redirect(url_for('admin_user_detail', user_id=user.id))

@app.route('/admin/users/<int:user_id>/adjust-balance', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_adjust_balance(user_id):
    """Ajuster le solde d'un utilisateur"""
    user = User.query.get_or_404(user_id)
    form = AdjustUserBalanceForm()
    
    if form.validate_on_submit():
        old_balance = user.balance
        user.balance += form.amount.data
        
        # Log la transaction d'ajustement
        db.session.commit()
        
        log_audit('ADMIN_BALANCE_ADJUST',
                 f'Ajustement de solde: {user.username} de {old_balance} à {user.balance} ({form.reason.data})',
                 status='success')
        
        flash(f'Solde de {user.username} ajusté de {form.amount.data:.2f} DA', 'success')
        return redirect(url_for('admin_user_detail', user_id=user.id))
    
    return render_template('admin/adjust_balance.html', user=user, form=form)

@app.route('/admin/transactions')
@login_required
@role_required('admin')
def admin_transactions():
    """Voir toutes les transactions"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    
    query = Transaction.query
    if search:
        # Rechercher par username ou email
        query = query.join(User, Transaction.sender_id == User.id).filter(
            User.username.contains(search) | User.email.contains(search)
        )
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    transactions = query.order_by(Transaction.created_at.desc()).paginate(page=page, per_page=50)
    
    log_audit('ADMIN_TRANSACTIONS_VIEW', 'Consultation des transactions')
    
    return render_template('admin/transactions.html', transactions=transactions, search=search, status_filter=status_filter)

@app.route('/admin/reports')
@login_required
@role_required('admin')
def admin_reports():
    """Rapports et statistiques"""
    # Statistiques globales
    total_users = User.query.count()
    total_pdv = User.query.filter_by(role='pdv').count()
    total_clients = User.query.filter_by(role='client').count()
    
    total_transactions = Transaction.query.count()
    total_volume = db.session.query(db.func.sum(Transaction.amount)).scalar() or 0
    total_balance = db.session.query(db.func.sum(User.balance)).scalar() or 0
    
    # Transactions par jour (dernier mois)
    from sqlalchemy import func
    daily_stats = db.session.query(
        func.date(Transaction.created_at).label('date'),
        func.count(Transaction.id).label('count'),
        func.sum(Transaction.amount).label('amount')
    ).filter(
        Transaction.created_at >= datetime.utcnow() - timedelta(days=30)
    ).group_by(func.date(Transaction.created_at)).order_by('date').all()
    
    log_audit('ADMIN_REPORTS_VIEW', 'Accès aux rapports')
    
    return render_template('admin/reports.html',
                         total_users=total_users,
                         total_pdv=total_pdv,
                         total_clients=total_clients,
                         total_transactions=total_transactions,
                         total_volume=total_volume,
                         total_balance=total_balance,
                         daily_stats=daily_stats)

@app.route('/admin/operators')
@login_required
@role_required('admin')
def admin_operators():
    """Gestion des opérateurs"""
    operators = Operator.query.all()
    return render_template('admin/operators.html', operators=operators)

@app.route('/admin/operators/add', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_add_operator():
    """Ajouter un opérateur"""
    form = AddOperatorForm()
    if form.validate_on_submit():
        operator = Operator(
            name=form.name.data,
            code=form.code.data,
            description=form.description.data
        )
        db.session.add(operator)
        db.session.commit()
        
        log_audit('ADMIN_OPERATOR_ADD', f'Opérateur créé: {operator.name}')
        
        flash(f'Opérateur {operator.name} créé!', 'success')
        return redirect(url_for('admin_operators'))
    
    return render_template('admin/add_operator.html', form=form)

@app.route('/admin/operators/<int:op_id>/toggle', methods=['POST'])
@login_required
@role_required('admin')
def admin_toggle_operator(op_id):
    """Activer/Désactiver un opérateur"""
    operator = Operator.query.get_or_404(op_id)
    operator.is_active = not operator.is_active
    db.session.commit()
    
    status = 'activé' if operator.is_active else 'désactivé'
    log_audit('ADMIN_OPERATOR_TOGGLE', f'Opérateur {operator.name} {status}')
    
    flash(f'Opérateur {operator.name} {status}!', 'success')
    return redirect(url_for('admin_operators'))

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_settings():
    """Paramètres système"""
    form = SystemSettingForm()
    
    if form.validate_on_submit():
        set_setting('commission_rate', form.commission_rate.data, 'number', 'Taux de commission')
        set_setting('max_transaction', form.max_transaction.data, 'number', 'Montant max par transaction')
        set_setting('min_transaction', form.min_transaction.data, 'number', 'Montant min par transaction')
        
        log_audit('ADMIN_SETTINGS_UPDATE', 'Paramètres système mis à jour')
        
        flash('Paramètres sauvegardés!', 'success')
        return redirect(url_for('admin_settings'))
    
    elif request.method == 'GET':
        form.commission_rate.data = get_setting('commission_rate', 2.0)
        form.max_transaction.data = get_setting('max_transaction', 1000000)
        form.min_transaction.data = get_setting('min_transaction', 100)
    
    return render_template('admin/settings.html', form=form)

@app.route('/admin/audit-logs')
@login_required
@role_required('admin')
def admin_audit_logs():
    """Voir les logs d'audit"""
    page = request.args.get('page', 1, type=int)
    user_filter = request.args.get('user_id', '')
    
    query = AuditLog.query
    if user_filter:
        query = query.filter_by(user_id=user_filter)
    
    logs = query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=50)
    
    return render_template('admin/audit_logs.html', logs=logs, user_filter=user_filter)

# ==================== Routes d'erreur ====================

@app.errorhandler(404)
def not_found_error(error):
    """Erreur 404"""
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Erreur 500"""
    db.session.rollback()
    return render_template('errors/500.html'), 500

@app.errorhandler(403)
def forbidden_error(error):
    """Erreur 403"""
    return render_template('errors/403.html'), 403

# ==================== Contexte template ====================

@app.context_processor
def inject_user():
    """Injecter l'utilisateur dans le contexte global"""
    return {
        'current_user': current_user,
        'now': datetime.utcnow()
    }

# ==================== Commandes CLI ====================

@app.cli.command()
def init_db():
    """Initialiser la base de données"""
    db.create_all()
    
    # Ajouter les opérateurs par défaut
    if Operator.query.first() is None:
        operators = [
            Operator(name='Djezzy', code='djz', description='Opérateur Djezzy'),
            Operator(name='Nedjma', code='ndj', description='Opérateur Nedjma'),
            Operator(name='Mobilis', code='mob', description='Opérateur Mobilis')
        ]
        for op in operators:
            db.session.add(op)
        db.session.commit()
    
    print('Base de données initialisée avec succès!')

@app.cli.command()
def create_demo():
    """Créer des données de démo"""
    db.drop_all()
    db.create_all()
    
    # Créer les opérateurs par défaut
    operators = [
        Operator(name='Djezzy', code='djz', description='Opérateur Djezzy'),
        Operator(name='Nedjma', code='ndj', description='Opérateur Nedjma'),
        Operator(name='Mobilis', code='mob', description='Opérateur Mobilis')
    ]
    for op in operators:
        db.session.add(op)
    db.session.commit()
    
    # Créer un admin
    admin = User(username='admin', email='admin@topili.com', phone='0661111111', role='admin', balance=0)
    admin.set_password('admin123456')
    db.session.add(admin)
    db.session.commit()
    
    # Créer un PdV
    pdv = User(username='pdv_ali', email='ali@topili.com', phone='0661234567', role='pdv', balance=100000)
    pdv.set_password('pdv123456')
    db.session.add(pdv)
    db.session.commit()
    
    # Créer des clients
    for i in range(5):
        client = User(
            username=f'client_{i+1}',
            email=f'client{i+1}@topili.com',
            phone=f'066123456{i}',
            role='client',
            pdv_id=pdv.id,
            balance=5000
        )
        client.set_password('client123456')
        db.session.add(client)
    
    db.session.commit()
    print('Données de démo créées!')
    print('Admin - Username: admin, Mot de passe: admin123456')
    print('PdV - Username: pdv_ali, Mot de passe: pdv123456')
    print('Clients - Username: client_1 à client_5, Mot de passe: client123456')
    print('Opérateurs: Djezzy, Nedjma, Mobilis')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
