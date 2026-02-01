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
    
    # Tabla de Ventas (Cabecera Unificada)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            usuario_id INTEGER,
            tipo_documento TEXT,
            fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            subtotal REAL,
            igv_total REAL,
            total REAL,
            FOREIGN KEY (cliente_id) REFERENCES clientes (id),
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')

    # PARCHE DE SEGURIDAD: Intentar añadir cliente_id si la tabla se creó con la versión vieja
    try:
        cursor.execute('ALTER TABLE ventas ADD COLUMN cliente_id INTEGER')
    except:
        pass # La columna ya existe

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


#Agregar medicamento al inventario desde el formulario 1 x 1 
@app.route('/agregar', methods=['POST'])
@login_requerido
def agregar():
    if session.get('rol') != 'admin':
        return "Acceso denegado"
    
    # Captura de datos del formulario
    nombre = request.form['nombre'].strip().upper()
    codigo_lote = request.form['lote']
    cantidad = request.form['cantidad']
    vencimiento = request.form['vencimiento']
    precio = request.form['precio']
    # Si es un checkbox, Flask recibe '1' si está marcado, o None si no.
    afecto_igv = 1 if request.form.get('afecto_igv') else 0

    conexion = conectar_db()
    cursor = conexion.cursor()


    # 1. Insertar/Actualizar el producto con su estado de IGV
    cursor.execute('''
        INSERT INTO productos (nombre, afecto_igv) 
        VALUES (?, ?) 
        ON CONFLICT(nombre) DO UPDATE SET afecto_igv=excluded.afecto_igv
    ''', (nombre.upper(), afecto_igv))

    # 2. Obtener el ID del producto recién insertado o existente
    cursor.execute('SELECT id FROM productos WHERE nombre = ?', (nombre.upper(),))
    producto_id = cursor.fetchone()[0]

    # 3. Insertar el nuevo lote asociado al producto
    cursor.execute('''
        INSERT INTO lotes (producto_id, codigo_lote, stock, fecha_vence, precio)
        VALUES (?, ?, ?, ?, ?)
    ''', (producto_id, codigo_lote, int(cantidad), vencimiento, float(precio)))     


    conexion.commit()
    conexion.close()
    return redirect('/gestion_inventario')

# Necesitamos una ruta que lea el archivo, separe las columnas y haga el doble insert: primero en productos (si no existe) y luego en lotes
@app.route('/importar_stock', methods=['POST'])
@login_requerido
def importar_stock():
    if session.get('rol') != 'admin':
        return "Acceso denegado"
        
    archivo = request.files.get('archivo_txt')
    if not archivo or archivo.filename == '':
        return redirect('/gestion_inventario')

    conexion = conectar_db()
    cursor = conexion.cursor()
    
    try:
        # Leemos el contenido y lo decodificamos de forma simple
        contenido = archivo.read().decode('utf-8').strip().splitlines()
        print(f"DEBUG: Se leyeron {len(contenido)} líneas del archivo.")

        for num_linea, linea in enumerate(contenido, 1):
            linea = linea.strip()
            # Ignoramos líneas vacías o restos de formato RTF
            if not linea or linea.startswith('{') or linea.startswith('\\'):
                continue
            
            datos = [d.strip() for d in linea.split(',')]
            
            if len(datos) < 5:
                print(f"Línea {num_linea} saltada por falta de datos: {linea}")
                continue
            
            nombre, lote, stock, vence, precio = datos

            # 1. Insertar Producto
            cursor.execute('INSERT OR IGNORE INTO productos (nombre) VALUES (?)', (nombre.upper(),))
            cursor.execute('SELECT id FROM productos WHERE nombre = ?', (nombre.upper(),))
            producto_id = cursor.fetchone()[0]

            # 2. Insertar Lote
            cursor.execute('''
                INSERT INTO lotes (producto_id, codigo_lote, stock, fecha_vence, precio)
                VALUES (?, ?, ?, ?, ?)
            ''', (producto_id, lote, int(stock), vence, float(precio)))

        conexion.commit()
        print("IMPORTACIÓN EXITOSA")
        
    except Exception as e:
        conexion.rollback()
        print(f"ERROR EN IMPORTACIÓN (Línea {num_linea}): {str(e)}")
    finally:
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
        SELECT l.id, p.nombre, l.codigo_lote, l.stock, l.fecha_vence, l.precio
        FROM lotes l
        JOIN productos p ON l.producto_id = p.id
        WHERE l.stock > 0
        ORDER BY l.fecha_vence ASC
    '''
    cursor.execute(query)
    lotes_disponibles = cursor.fetchall()
    conexion.close()
    return render_template('ventas.html', lotes=lotes_disponibles)

# AGREGAR AQUÍ: Gestión del carrito temporal
@app.route('/agregar_al_carrito', methods=['POST'])
@login_requerido
def agregar_al_carrito():
    if 'carrito' not in session:
        session['carrito'] = []

    # Recibimos los datos y forzamos el tipo de dato
    lote_id = request.form.get('lote_id')
    nombre = request.form.get('nombre_mostrar')
    
    # Aquí estaba el fallo: forzamos int para cantidad y float para precio
    try:
        cantidad = int(request.form.get('cantidad', 1))
        precio = float(request.form.get('precio_unitario', 0.0))
    except (ValueError, TypeError):
        cantidad = 1
        precio = 0.0

    item = {
        'lote_id': lote_id,
        'nombre': nombre,
        'cantidad': cantidad,
        'precio': precio
    }
    
    carrito = session['carrito']
    carrito.append(item)
    session['carrito'] = carrito
    
    return redirect('/ventas')

# Ubicación: app.py, después de la ruta de agregar_al_carrito
@app.route('/limpiar_carrito')
@login_requerido
def limpiar_carrito():
    # Elimina la lista 'carrito' de la sesión del usuario
    session.pop('carrito', None)
    # Redirige de vuelta a la interfaz de ventas
    return redirect('/ventas')

@app.route('/procesar_venta', methods=['POST'])
@login_requerido
def procesar_venta():
    carrito = session.get('carrito', [])
    if not carrito:
        return "El carrito está vacío", 400

    # 1. Capturar datos del cliente y comprobante
    doc_cliente = request.form.get('doc_identidad')
    nombre_cliente = request.form.get('nombre_cliente')
    tipo_comprobante = request.form.get('tipo_comprobante') # 'Boleta' o 'Factura'
    
    conexion = conectar_db()
    cursor = conexion.cursor()
    
    try:
        # 2. Registrar/Actualizar Cliente
        cursor.execute('''
            INSERT INTO clientes (nombre_razon_social, documento_identidad, tipo_cliente) 
            VALUES (?, ?, ?)
            ON CONFLICT(documento_identidad) DO UPDATE SET nombre_razon_social=excluded.nombre_razon_social
        ''', (nombre_cliente, doc_cliente, tipo_comprobante))
        
        cursor.execute('SELECT id FROM clientes WHERE documento_identidad = ?', (doc_cliente,))
        cliente_id = cursor.fetchone()[0]

        # 3. Calcular Totales e IGV
        total_venta = sum(item['precio'] * item['cantidad'] for item in carrito)
        # Lógica: El precio de lista ya incluye IGV (18%)
        subtotal_venta = total_venta / 1.18
        igv_total = total_venta - subtotal_venta

        # 4. Insertar Cabecera de Venta
        cursor.execute('''
            INSERT INTO ventas (cliente_id, usuario_id, tipo_documento, subtotal, igv_total, total)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (cliente_id, session['usuario_id'], tipo_comprobante, subtotal_venta, igv_total, total_venta))
        
        venta_id = cursor.lastrowid

        # 5. Procesar cada ítem del carrito (Detalle y Stock)
        for item in carrito:
            # Insertar detalle
            subtotal_item = item['precio'] * item['cantidad']
            cursor.execute('''
                INSERT INTO detalle_ventas (venta_id, lote_id, cantidad, precio_unitario, subtotal_item)
                VALUES (?, ?, ?, ?, ?)
            ''', (venta_id, item['lote_id'], item['cantidad'], item['precio'], subtotal_item))

            # DESCUENTO DE STOCK: Restar la cantidad vendida del lote
            cursor.execute('UPDATE lotes SET stock = stock - ? WHERE id = ?', (item['cantidad'], item['lote_id']))

        conexion.commit()
        session.pop('carrito', None) # Limpiar carrito tras éxito
        return redirect('/ventas')

    except Exception as e:
        conexion.rollback()
        return f"Error al procesar la venta: {str(e)}", 500
    finally:
        conexion.close()

if __name__ == '__main__':
    inicializar_tablas()
    app.run(debug=True)