from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)

# Función para conectar a la base de datos
def conectar_db():
    conexion = sqlite3.connect('farmacia.db')
    return conexion

@app.route('/')
def home():
    conexion = conectar_db()
    cursor = conexion.cursor()
    # Aseguramos que la tabla exista para que no de error la primera vez
    cursor.execute('CREATE TABLE IF NOT EXISTS medicamentos (id INTEGER PRIMARY KEY, nombre TEXT, precio REAL)')
    
    # SQL para traer todos los registros
    cursor.execute('SELECT * FROM medicamentos')
    lista_medicamentos = cursor.fetchall()
    
    conexion.close()
    # Enviamos la lista al HTML
    return render_template('index.html', medicamentos=lista_medicamentos)

@app.route('/eliminar/<int:id>')
def eliminar(id):
    conexion = conectar_db()
    cursor = conexion.cursor()
    
    # SQL para eliminar por ID
    cursor.execute('DELETE FROM medicamentos WHERE id = ?', (id,))
    
    conexion.commit()
    conexion.close()
    return redirect('/')

@app.route('/agregar', methods=['POST'])
def agregar():
    nombre = request.form['nombre']
    lote = request.form['lote']
    cantidad = request.form['cantidad']
    vencimiento = request.form['vencimiento'] # Fecha del HTML
    precio = request.form['precio']

    conexion = conectar_db()
    cursor = conexion.cursor()
    
    # 1. Insertar o buscar el medicamento
    cursor.execute('INSERT OR IGNORE INTO medicamentos (nombre) VALUES (?)', (nombre,))
    
    # 2. Insertar el lote con su fecha
    cursor.execute('''
        INSERT INTO lotes (nombre_med, codigo_lote, stock, fecha_vence, precio) 
        VALUES (?, ?, ?, ?, ?)''', 
        (nombre, lote, cantidad, vencimiento, precio))
    
    conexion.commit()
    conexion.close()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)