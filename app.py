import sqlite3
from datetime import date
from functools import wraps
from flask import Flask, render_template, request, redirect, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# CONFIGURACIÓN DE SEGURIDAD
# Esta llave cifra las sesiones para que los roles no puedan ser alterados.
app.secret_key = 'wisbentech_secret_key_2026'

# --- UTILIDADES Y BASE DE DATOS ---

def conectar_db():
    """Establece la conexión con el archivo físico de la base de datos."""
    conexion = sqlite3.connect('farmacia.db')
    return conexion

def inicializar_tablas():
    """Crea la estructura normalizada de la base de datos al arrancar."""
    conexion = conectar_db()
    cursor = conexion.cursor()
    
    # Tabla Maestra de Productos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE
        )
    ''')

    # Tabla de Lotes (Relacionada con productos)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER,
            codigo_lote TEXT NOT NULL,
            stock INTEGER NOT NULL,
            fecha_vence DATE NOT NULL,
            precio REAL,
            FOREIGN KEY (producto_id) REFERENCES productos (id)
        )
    ''')
    
    # Tabla de Usuarios y Roles
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            rol TEXT NOT NULL 
        )
    ''')
    
    # Tabla de Ventas para historial
    cursor.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP, total REAL)')
    
    # Creamos un admin por defecto si la tabla está vacía (Pass: admin123)
    cursor.execute('SELECT COUNT(*) FROM usuarios')
    if cursor.fetchone()[0] == 0:
        password_segura = generate_password_hash('admin123')
        cursor.execute('INSERT INTO usuarios (username, password, rol) VALUES (?, ?, ?)',
                       ('admin', password_segura, 'admin'))
    
    conexion.commit()
    conexion.close()

# --- DECORADORES DE SEGURIDAD ---

def login_requerido(f):
    """Restringe el acceso a usuarios que no hayan iniciado sesión."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

# --- RUTAS DE AUTENTICACIÓN ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pw = request.form['password']
        
        conexion = conectar_db()
        cursor = conexion.cursor()
        cursor.execute('SELECT id, password, rol FROM usuarios WHERE username = ?', (user,))
        resultado = cursor.fetchone()
        conexion.close()
        
        if resultado and check_password_hash(resultado[1], pw):
            session['usuario_id'] = resultado[0]
            session['username'] = user
            session['rol'] = resultado[2]
            return redirect('/')
        else:
            return "<h1>Error: Usuario o contraseña incorrectos</h1><a href='/login'>Reintentar</a>"

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/crear_usuario', methods=['GET', 'POST'])
@login_requerido
def crear_usuario():
    # Solo el admin puede gestionar personal
    if session.get('rol') != 'admin':
        return "Acceso denegado"
        
    if request.method == 'POST':
        nuevo_user = request.form['username']
        # Hasheamos la clave inmediatamente por seguridad
        nuevo_pw = generate_password_hash(request.form['password'])
        rol = request.form['rol']
        
        conexion = conectar_db()
        cursor = conexion.cursor()
        try:
            cursor.execute('INSERT INTO usuarios (username, password, rol) VALUES (?, ?, ?)',
                           (nuevo_user, nuevo_pw, rol))
            conexion.commit()
        except:
            return "El usuario ya existe"
        finally:
            conexion.close()
        return redirect('/')
        
    return render_template('crear_usuario.html')

# --- RUTAS DE INVENTARIO (Solo Admin) ---

@app.route('/')
@login_requerido
def home():
    return render_template('index.html')

@app.route('/gestion_inventario')
@login_requerido
def gestion_inventario():
    if session.get('rol') != 'admin':
        return "Acceso denegado"
    
    conexion = conectar_db()
    cursor = conexion.cursor()
    query = '''
        SELECT l.id, p.nombre, l.codigo_lote, l.stock, l.fecha_vence, l.precio 
        FROM lotes l
        JOIN productos p ON l.producto_id = p.id
    '''
    cursor.execute(query)
    lista_lotes = cursor.fetchall()
    conexion.close()
    hoy = date.today().strftime('%Y-%m-%d')
    return render_template('inventario_tabla.html', medicamentos=lista_lotes, fecha_actual=hoy)

@app.route('/agregar', methods=['POST'])
@login_requerido
def agregar():
    if session.get('rol') != 'admin':
        return "Acceso denegado: Solo administradores pueden cargar stock."
    
    nombre = request.form['nombre'].strip().upper()
    codigo_lote = request.form['lote']
    cantidad = request.form['cantidad']
    vencimiento = request.form['vencimiento']
    precio = request.form['precio']

    conexion = conectar_db()
    cursor = conexion.cursor()
    cursor.execute('INSERT OR IGNORE INTO productos (nombre) VALUES (?)', (nombre,))
    cursor.execute('SELECT id FROM productos WHERE nombre = ?', (nombre,))
    producto_id = cursor.fetchone()[0]
    
    cursor.execute('''
        INSERT INTO lotes (producto_id, codigo_lote, stock, fecha_vence, precio) 
        VALUES (?, ?, ?, ?, ?)''', 
        (producto_id, codigo_lote, cantidad, vencimiento, precio))
    
    conexion.commit()
    conexion.close()
    return redirect('/')

@app.route('/eliminar/<int:id>')
@login_requerido
def eliminar(id):
    if session.get('rol') != 'admin':
        return "Acceso denegado."
    
    conexion = conectar_db()
    cursor = conexion.cursor()
    cursor.execute('DELETE FROM lotes WHERE id = ?', (id,))
    conexion.commit()
    conexion.close()
    return redirect('/')

# --- RUTAS DE VENTAS (Admin y Vendedor) ---

@app.route('/ventas')
@login_requerido
def ventas():
    conexion = conectar_db()
    cursor = conexion.cursor()
    query = '''
        SELECT l.id, p.nombre, l.codigo_lote, l.stock, l.fecha_vence 
        FROM lotes l
        JOIN productos p ON l.producto_id = p.id
        WHERE l.stock > 0
        ORDER BY l.fecha_vence ASC
    '''
    cursor.execute(query)
    lotes_disponibles = cursor.fetchall()
    conexion.close()
    return render_template('ventas.html', lotes=lotes_disponibles)

@app.route('/procesar_venta', methods=['POST'])
@login_requerido
def procesar_venta():
    lote_id_referencia = request.form['lote_id'] 
    cantidad_a_vender = int(request.form['cantidad'])

    conexion = conectar_db()
    cursor = conexion.cursor()

    # Buscamos todos los lotes del mismo producto para aplicar PEPS
    query = """
        SELECT id, stock FROM lotes 
        WHERE producto_id = (SELECT producto_id FROM lotes WHERE id = ?) 
        AND stock > 0 
        ORDER BY fecha_vence ASC
    """
    cursor.execute(query, (lote_id_referencia,))
    lotes = cursor.fetchall()

    total_disponible = sum(lote[1] for lote in lotes)

    if total_disponible >= cantidad_a_vender:
        for lote_id, stock_lote in lotes:
            if cantidad_a_vender <= 0: break
            
            if stock_lote <= cantidad_a_vender:
                cantidad_a_vender -= stock_lote
                cursor.execute("UPDATE lotes SET stock = 0 WHERE id = ?", (lote_id,))
            else:
                nuevo_stock = stock_lote - cantidad_a_vender
                cursor.execute("UPDATE lotes SET stock = ? WHERE id = ?", (nuevo_stock, lote_id))
                cantidad_a_vender = 0
        
        cursor.execute('INSERT INTO ventas (total) VALUES (?)', (0,))
        conexion.commit()
    else:
        conexion.close()
        return "<h1>Error: Stock insuficiente total</h1><a href='/ventas'>Volver</a>"

    conexion.close()
    return redirect('/')

if __name__ == '__main__':
    inicializar_tablas()
    app.run(debug=True)