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
    
    # Tabla de Lotes (Ajustada para que coincida con tu lógica de 'agregar')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_med TEXT NOT NULL,
            codigo_lote TEXT NOT NULL,
            stock INTEGER NOT NULL,
            fecha_vence DATE NOT NULL,
            precio REAL
        )
    ''')
    
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

if __name__ == '__main__':
    # IMPORTANTE: Llamamos a la creación de tablas antes de iniciar el servidor
    inicializar_tablas()
    app.run(debug=True)