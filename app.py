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

@app.route('/agregar', methods=['POST'])
def agregar():
    nombre = request.form['nombre']
    precio = request.form['precio']

    conexion = conectar_db()
    cursor = conexion.cursor()
    # Creamos la tabla si no existe (SQL básico)
    cursor.execute('CREATE TABLE IF NOT EXISTS medicamentos (id INTEGER PRIMARY KEY, nombre TEXT, precio REAL)')
    # Insertamos los datos
    cursor.execute('INSERT INTO medicamentos (nombre, precio) VALUES (?, ?)', (nombre, precio))
    
    conexion.commit()
    conexion.close()
    
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)