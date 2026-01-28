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

    # Tabla de Impuestos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS impuestos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL, -- Ej: IGV
            valor REAL NOT NULL,   -- Ej: 18.0
            activo INTEGER DEFAULT 1 -- 1 para el actual, 0 para históricos
        )
    ''')

    # Insertamos el IGV actual de Perú si la tabla está vacía
    cursor.execute('SELECT COUNT(*) FROM impuestos')
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO impuestos (nombre, valor) VALUES (?, ?)', ('IGV', 18.0))

    # Tabla Maestra de Productos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE
        )
    ''')
    # Nota: Si la tabla ya existe, usaremos un bloque TRY para añadir la columna
    try:
        cursor.execute('ALTER TABLE productos ADD COLUMN afecto_igv INTEGER DEFAULT 1')
    except:
        pass # La columna ya existe


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
    
    # Tabla de Clientes (Persona Natural o Jurídica)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_razon_social TEXT NOT NULL,
            documento_identidad TEXT UNIQUE NOT NULL, -- DNI o RUC
            tipo_cliente TEXT NOT NULL -- 'Natural' o 'Juridica'
        )
    ''')

    # Tabla de Ventas (Cabecera)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            usuario_id INTEGER,
            tipo_documento TEXT, -- 'Boleta' o 'Factura'
            fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            subtotal REAL,
            igv_total REAL,
            total REAL,
            FOREIGN KEY (cliente_id) REFERENCES clientes (id),
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')

    # Tabla Detalle de Venta (Para registrar qué productos van en cada boleta/factura)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS detalle_ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id INTEGER,
            lote_id INTEGER,
            cantidad INTEGER,
            precio_unitario REAL,
            subtotal_item REAL,
            FOREIGN KEY (venta_id) REFERENCES ventas (id),
            FOREIGN KEY (lote_id) REFERENCES lotes (id)
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
    
    # Insertar IGV actual si la tabla está vacía
        cursor.execute('SELECT COUNT(*) FROM impuestos')
        if cursor.fetchone()[0] == 0:
            cursor.execute('INSERT INTO impuestos (nombre, valor) VALUES (?, ?)', ('IGV', 18.0))

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
    return redirect('/gestion_inventario')

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
    return redirect('/gestion_inventario')

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
    # ... (Captura de datos del formulario) ...
    lote_id = request.form['lote_id']
    cantidad = int(request.form['cantidad'])
    
    conexion = conectar_db()
    cursor = conexion.cursor()
    
    # 1. Obtenemos precio y si el producto es afecto al IGV
    query = """
        SELECT l.precio, p.afecto_igv, p.nombre 
        FROM lotes l 
        JOIN productos p ON l.producto_id = p.id 
        WHERE l.id = ?
    """
    cursor.execute(query, (lote_id,))
    lote_info = cursor.fetchone()
    
    precio_unitario = lote_info[0]
    es_afecto = lote_info[1]
    
    # 2. Cálculos matemáticos
    # Si el precio ya incluye IGV, desglosamos: Subtotal = Total / 1.18
    # Si el precio es base, sumamos: Total = Subtotal * 1.18
    # Usaremos la lógica de "Precio de lista ya incluye IGV" (Común en farmacias)
    
    total_item = precio_unitario * cantidad
    
    if es_afecto == 1:
        # Desglose de impuestos (18%)
        subtotal = total_item / 1.18
        igv_calculado = total_item - subtotal
    else:
        # Producto exonerado o inafecto
        subtotal = total_item
        igv_calculado = 0.0

    # ... (Aquí seguiría la lógica de insertar en tablas 'ventas' y 'detalle_ventas') ...
    
    conexion.commit()
    conexion.close()
    return redirect('/ventas')

if __name__ == '__main__':
    inicializar_tablas()
    app.run(debug=True)