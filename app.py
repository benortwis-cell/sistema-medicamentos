from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)

def conectar_db():
    # Establece la conexión con el archivo de base de datos
    conexion = sqlite3.connect('farmacia.db')
    return conexion

def inicializar_tablas():
    conexion = conectar_db()
    cursor = conexion.cursor()
    
    # Habilitamos claves foráneas para la integridad de los datos
    cursor.execute('PRAGMA foreign_keys = ON;')

    # 1. Tabla Maestra de Productos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE
        )
    ''')

    # 2. Tabla de Lotes (Relacionada con productos)
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
    
    # 3. Tablas para Ventas (Para tu análisis futuro)
    cursor.execute('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP, total REAL)')
    
    conexion.commit()
    conexion.close()


@app.route('/')
def home():
    conexion = conectar_db()
    cursor = conexion.cursor()
    
    # Usamos JOIN para traer el nombre desde la tabla productos
    query = '''
        SELECT l.id, p.nombre, l.codigo_lote, l.stock, l.fecha_vence, l.precio 
        FROM lotes l
        JOIN productos p ON l.producto_id = p.id
    '''
    cursor.execute(query)
    lista_lotes = cursor.fetchall()
    
    conexion.close()
    return render_template('index.html', medicamentos=lista_lotes)

@app.route('/agregar', methods=['POST'])
def agregar():
    nombre = request.form['nombre'].strip().upper() # Estandarizamos a mayúsculas
    codigo_lote = request.form['lote']
    cantidad = request.form['cantidad']
    vencimiento = request.form['vencimiento']
    precio = request.form['precio']

    conexion = conectar_db()
    cursor = conexion.cursor()
    
    # 1. Lógica de Producto: Insertamos solo si no existe
    cursor.execute('INSERT OR IGNORE INTO productos (nombre) VALUES (?)', (nombre,))
    
    # Obtenemos el ID del producto (sea nuevo o existente)
    cursor.execute('SELECT id FROM productos WHERE nombre = ?', (nombre,))
    producto_id = cursor.fetchone()[0]
    
    # 2. Lógica de Lote: Lo vinculamos al ID del producto
    cursor.execute('''
        INSERT INTO lotes (producto_id, codigo_lote, stock, fecha_vence, precio) 
        VALUES (?, ?, ?, ?, ?)''', 
        (producto_id, codigo_lote, cantidad, vencimiento, precio))
    
    conexion.commit()
    conexion.close()
    return redirect('/')

@app.route('/eliminar/<int:id>')
def eliminar(id):
    conexion = conectar_db()
    cursor = conexion.cursor()
    # Eliminamos del inventario de lotes
    cursor.execute('DELETE FROM lotes WHERE id = ?', (id,))
    conexion.commit()
    conexion.close()
    return redirect('/')

from datetime import datetime

@app.route('/ventas')
def ventas():
    conexion = conectar_db()
    cursor = conexion.cursor()
    # Traemos solo lotes con stock, ordenados por fecha de vencimiento (PEPS)
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
def procesar_venta():
    # Obtenemos el ID del producto (ahora la venta es por producto, no por un lote fijo)
    # Nota: Asegúrate de que el select en tu HTML envíe el producto_id
    producto_id = request.form['lote_id'] 
    cantidad_a_vender = int(request.form['cantidad'])

    conexion = conectar_db()
    cursor = conexion.cursor()

    # 1. Buscamos TODOS los lotes de ese medicamento que tengan stock
    # Los ordenamos por fecha de vencimiento (PEPS) para minimizar pérdidas
    query = """
        SELECT id, stock FROM lotes 
        WHERE producto_id = (SELECT producto_id FROM lotes WHERE id = ?) 
        AND stock > 0 
        ORDER BY fecha_vence ASC
    """
    cursor.execute(query, (producto_id,))
    lotes = cursor.fetchall()

    # Calculamos el total disponible sumando todos los lotes
    total_disponible = sum(lote[1] for lote in lotes)

    # Solo procedemos si el total de TODOS los lotes cubre la venta
    if total_disponible >= cantidad_a_vender:
        for lote_id, stock_lote in lotes:
            if cantidad_a_vender <= 0:
                break
            
            if stock_lote <= cantidad_a_vender:
                # Caso A: El lote no alcanza para cubrir todo, lo agotamos y seguimos al siguiente
                cantidad_a_vender -= stock_lote
                cursor.execute("UPDATE lotes SET stock = 0 WHERE id = ?", (lote_id,))
            else:
                # Caso B: El lote tiene suficiente para cubrir lo que falta de la venta
                nuevo_stock = stock_lote - cantidad_a_vender
                cursor.execute("UPDATE lotes SET stock = ? WHERE id = ?", (nuevo_stock, lote_id))
                cantidad_a_vender = 0
        
        # Registramos el movimiento en la tabla de ventas para tu análisis
        cursor.execute('INSERT INTO ventas (total) VALUES (?)', (0,)) # Puedes calcular el total después
        conexion.commit()
    else:
        # Aquí puedes retornar un mensaje de error si ni sumando todos los lotes alcanza
        conexion.close()
        return "<h1>Error: Stock insuficiente en todos los lotes combinados</h1><a href='/ventas'>Volver</a>"

    conexion.close()
    return redirect('/')

if __name__ == '__main__':
    # IMPORTANTE: Llamamos a la creación de tablas antes de iniciar el servidor
    inicializar_tablas()
    app.run(debug=True)