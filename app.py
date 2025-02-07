from flask import Flask, render_template, url_for, request, redirect,jsonify
import sqlite3

app = Flask(__name__)

@app.route('/')
def omega():
    return render_template('omega.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/savoir')
def savoir():
    return render_template('savoir.html')

@app.route('/prof')
def profinfo():
    return render_template('prof.html')



@app.route('/etudiant', methods=['GET','POST'])
def etudiant_login():
    if request.method == 'POST':
        CNE = request.form.get('CNE')
        nom = request.form.get('nom')

        connection = sqlite3.connect('data.db')
        cursor = connection.cursor()
        cursor.execute('''
            SELECT * FROM registrations
            WHERE CNE = ? AND nom = ?
        ''', (CNE, nom))

        etudiant = cursor.fetchone()

        connection.close()

        if etudiant:
            connection = sqlite3.connect('data.db')
            cursor = connection.cursor()

            cursor.execute('''
                SELECT * FROM salle
                WHERE idgroupe = ?
            ''', (etudiant[11],))
            salle_info = cursor.fetchone()

            connection.close()

            if salle_info:
               return render_template('etudinfo.html', etudiant=etudiant, salle_info=salle_info)
            else:
               return render_template('etudiant.html', error_message='Information de salle non disponible. Veuillez réessayer.')
        else:
            return render_template('etudiant.html', error_message='CNE ou nom incorrect. Veuillez réessayer.')

    return render_template('etudiant.html')

@app.route('/etudinfo')
def etudinfo():
    return render_template('etudinfo.html')

@app.route('/afficher_etudiants')
def afficher_etudiants():
    connection = sqlite3.connect('data.db')
    cursor = connection.cursor()

    cursor.execute('SELECT * FROM registrations')
    etudiants = cursor.fetchall()

    connection.close()

    return render_template('etudiantlist.html', etudiants=etudiants)

@app.route('/supprimer_etudiant/<int:etudiant_id>', methods=['POST'])
def supprimer_etudiant(etudiant_id):
    connection = sqlite3.connect('data.db')
    cursor = connection.cursor()

    cursor.execute("SELECT group_id FROM registrations WHERE id = ?", (etudiant_id,))
    group_id = cursor.fetchone()[0]

    cursor.execute("UPDATE groups SET capacity = capacity - 1 WHERE id = ?", (group_id,))

    cursor.execute("DELETE FROM registrations WHERE id = ?", (etudiant_id,))

    connection.commit()
    connection.close()

    return redirect(url_for('afficher_etudiants'))

@app.route('/rechercher_etudiant', methods=['GET'])
def rechercher_etudiant():
    critere = request.args.get('critere')
    search_term = request.args.get('search_term')

    connection = sqlite3.connect('data.db')
    cursor = connection.cursor()

    query = f"SELECT * FROM registrations WHERE {critere} LIKE ?"
    cursor.execute(query, ('%' + search_term + '%',))
    etudiants = cursor.fetchall()

    connection.close()

    return render_template('etudiantlist.html', etudiants=etudiants)


@app.route('/contact')
def contact():
    return render_template('contact.html')
@app.route('/paiement')
def afficher_paiement():
    return render_template('paiement.html')

@app.route('/inscription', methods=['GET', 'POST'])
def inscription():
    return render_template('inscription.html')

waiting_students = []

def create_group(cursor, typeetud, niveau):
    cursor.execute('''
        INSERT INTO groups (type, niveau, capacity)
        VALUES (?, ?, ?)
    ''', (typeetud, niveau, 0))
    group_id = cursor.lastrowid
    return group_id

def assign_student_to_group(cursor, group_id, student_data):
    cursor.execute('''
        INSERT INTO registrations (nom, prenom, email, CNE, choix, type, niveau, matiere, langue, formation, group_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,  ?, ?)
    ''', student_data)
    cursor.execute('''
        UPDATE groups
        SET capacity = capacity + 1
        WHERE id = ?
    ''', (group_id,))

def reserve_room(cursor, group_id):
    cursor.execute('''
        SELECT id, heure_debut, heure_fin, jour
        FROM salle
        WHERE idgroupe IS NULL
        LIMIT 1
    ''')
    salle_info = cursor.fetchone()

    if salle_info:
        # Check if the group already has a room reserved
        cursor.execute('''
            SELECT idgroupe
            FROM salle
            WHERE idgroupe = ?
        ''', (group_id,))
        existing_reservation = cursor.fetchone()

        if not existing_reservation:
            # Reserve the room for the group
            cursor.execute('''
                UPDATE salle
                SET idgroupe = ?
                WHERE id = ?
            ''', (group_id, salle_info[0]))

            cursor.execute('''
                UPDATE groups
                SET heure_debut = ?, heure_fin = ?, jour = ?
                WHERE id = ?
            ''', (salle_info[1], salle_info[2], salle_info[3], group_id))
            
def assign_professor_to_group(cursor, group_id, id_prof):
    cursor.execute('''
        UPDATE groups
        SET id_prof = ?
        WHERE id = ?
    ''', (id_prof, group_id))
    
@app.route('/traitement', methods=['POST'])
def traitement():
    global waiting_students
    nom = request.form['nom']
    prenom = request.form['prenom']
    email = request.form['email']
    choix = request.form['choix']
    CNE = request.form['CNE']
    type_etablissement = request.form['type']
    niveau = request.form['niveau']
    matiere = request.form.get('matiere', None)
    langue = request.form.get('langue', None)
    formation = request.form.get('formation', None)

    connection = sqlite3.connect('data.db')
    cursor = connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='registrations'")
    table_exists = cursor.fetchone()

    if not table_exists:
        init_db()

    if matiere is not None:
        typeetud = matiere
    elif formation is not None:
        typeetud = formation
    else:
        typeetud = langue

    cursor.execute('''
        SELECT id FROM registrations
        WHERE email = ? AND nom = ? AND prenom = ? AND CNE=? AND (matiere = ? OR formation = ? OR langue = ?)
    ''', (email, nom, prenom,CNE, typeetud, typeetud, typeetud))

    existing_student = cursor.fetchone()

    if existing_student:
        connection.close()
        return render_template('already_registered.html', nom=nom, prenom=prenom, email=email,CNE=CNE,typeetud=typeetud)

    student_id = None

    cursor.execute('''
        SELECT id, capacity FROM groups
        WHERE type = ? AND niveau = ? AND capacity < 8
    ''', (typeetud, niveau))

    group_data = cursor.fetchone()

    if group_data:
        group_id, group_capacity = group_data

        if group_capacity < 8:
            assign_student_to_group(cursor, group_id, (nom, prenom, email, CNE, choix, type_etablissement, niveau,  matiere, langue, formation, group_id))

            if group_capacity == 3:
                reserve_room(cursor, group_id)
                cursor.execute('''
                    SELECT IDprof FROM professeur
                    WHERE type_prof = ?
                ''', (typeetud,))

                id_prof = cursor.fetchone()

                if id_prof:
                    assign_professor_to_group(cursor, group_id, id_prof[0])

    else:
        group_id = create_group(cursor, typeetud, niveau)
        assign_student_to_group(cursor, group_id, (nom, prenom, email, CNE, choix, type_etablissement, niveau, matiere, langue, formation, group_id))

    connection.commit()
    connection.close()

    return render_template('traitement.html', nom=nom, prenom=prenom, email=email,typeetud=typeetud, choix=choix, student_id=student_id)




@app.route('/menugestion')
def menugestion():
    return render_template('menugestion.html')

@app.route('/traiter_code_secret', methods=['POST'])
def traiter_code_secret():
    entered_code = request.form.get('secretCode')
    correct_code = '2023'

    if entered_code == correct_code:
        return redirect(url_for('menugestion'))
    else:
        return render_template('etudiant.html', error_message='Code secret incorrect. Veuillez réessayer.')

def get_salle_data():
    connection = sqlite3.connect('data.db')
    cursor = connection.cursor()

    cursor.execute('SELECT * FROM salle ORDER BY jour, heure_debut')

    rows = cursor.fetchall()

    connection.close()

    data = {}
    for row in rows:
        day = row[5]  
        time_slot = f"{row[3]}-{row[4]}" 
        salle_info = {'idgroupe': row[2]}  

        if day not in data:
            data[day] = {}
        if time_slot not in data[day]:
            data[day][time_slot] = {}
        data[day][time_slot][row[1]] = salle_info  

    return data

@app.route('/salle')
def salle():
    data = get_salle_data()
    return render_template('salle.html', data=data)

@app.route('/groupe')
def groupe():
    connection = sqlite3.connect('data.db')
    cursor = connection.cursor()

    cursor.execute('SELECT id, type, niveau,id_prof, heure_debut, heure_fin, jour, capacity FROM groups')
    groupes = cursor.fetchall()

    connection.close()

    return render_template('groupe.html', groupes=groupes)


@app.route('/absence', endpoint='absence', methods=['GET', 'POST'])
def absence():
    connection = sqlite3.connect('data.db')
    cursor = connection.cursor()

    cursor.execute('SELECT id, type, niveau FROM groups')
    groups = cursor.fetchall()

    students = None

    if request.method == 'POST':
        group_id = request.form.get('group_id')
        cursor.execute('''
            SELECT id, nom, prenom FROM registrations
            WHERE group_id = ? 
        ''', (group_id,))
        students = cursor.fetchall()

    connection.close()

    return render_template('absence.html', groups=groups, students=students)

@app.route('/submit_absence', methods=['POST'])
def submit_absence():
    student_ids = request.form.getlist('student_ids')  # Récupérer la liste des étudiants sélectionnés
    date = request.form['date']

    connection = sqlite3.connect('data.db')
    cursor = connection.cursor()

    for student_id in student_ids:
        cursor.execute('''
            SELECT id FROM absence
            WHERE student_id = ?
        ''', (student_id,))
        existing_absence = cursor.fetchone()

        if existing_absence:
            cursor.execute('''
                UPDATE paiement
                SET sessions_payer = sessions_payer - 1
                WHERE student_id = ?
            ''', (student_id,))
        else:
            pass

        cursor.execute('''
            INSERT INTO absence (student_id, date)
            VALUES (?, ?)
        ''', (student_id, date))

    connection.commit()
    connection.close()

    return 'Success'


@app.route('/submit_presence', methods=['POST'])
def submit_presence():
    student_ids = request.form.getlist('student_ids')  # Récupérer la liste des étudiants sélectionnés
    date = request.form['date']

    connection = sqlite3.connect('data.db')
    cursor = connection.cursor()

    for student_id in student_ids:
        cursor.execute('''
            INSERT INTO presence (etudiant_id, date_presence)
            VALUES (?, ?)
        ''', (student_id, date))
        cursor.execute('''
            UPDATE paiement
            SET sessions_payer = sessions_payer - 1
            WHERE student_id = ?
        ''', (student_id,))


    connection.commit()
    connection.close()

    return 'Success'



@app.route('/get_groups', methods=['GET'])
def get_groups():
    connection = sqlite3.connect('data.db')
    cursor = connection.cursor()

    cursor.execute('SELECT id, type, niveau FROM groups')
    groups = cursor.fetchall()

    connection.close()

    options_html = ''
    for group in groups:
        options_html += f'<option value="{group[0]}">{group[1]} - {group[2]}</option>'

    return options_html



@app.route('/get_students', methods=['POST'])
def get_students():
    group_id = request.form.get('group_id')

    connection = sqlite3.connect('data.db')
    cursor = connection.cursor()

    cursor.execute('''
        SELECT id, nom, prenom FROM registrations
        WHERE group_id = ?
    ''', (group_id,))
    students = cursor.fetchall()

    connection.close()

    options_html = ''
    for student in students:
        options_html += f'<option value="{student[0]}">{student[1]} {student[2]}</option>'

    return options_html


@app.route('/paiement', methods=['POST'])
def paiement():
    if request.method == 'POST':
        student_id = request.json.get('id')
        montant=request.json.get('montant')
        payment_date = request.json.get('date_paiement')
        sessions_to_pay = request.json.get('sessions_payer')
        type_de_seance=request.json.get('type_de_seance')

        connection = sqlite3.connect('data.db')
        cursor = connection.cursor()

        cursor.execute('''
            INSERT INTO paiement (student_id,montant,date_paiement, sessions_payer,type_de_seance)
            VALUES (?, ?, ?,?,?)
        ''', (student_id,montant, payment_date, sessions_to_pay,type_de_seance))
        if sessions_to_pay == 0:
            alert_message = 'Le paiement a expiré pour cet étudiant.'
            print(alert_message)  

        elif sessions_to_pay == -1:
            cursor.execute('DELETE FROM registrations WHERE id = ?', (student_id,))
            print('Étudiant supprimé de la base de données.')


        connection.commit()

        connection.close()

        return 'Paiement enregistré avec succès', 200
    else:
        return 'Méthode non autorisée', 405
    return render_template('paiement.html')

    
@app.route('/afficher_professeurs')
def afficher_professeurs():
    connection = sqlite3.connect('data.db')
    cursor = connection.cursor()

    cursor.execute('SELECT * FROM professeur')
    professeurs = cursor.fetchall()

    connection.close()

    return render_template('professeur.html', professeurs=professeurs)

@app.route('/rechercher_professeur', methods=['GET'])
def rechercher_professeur():
    critere = request.args.get('critere')
    search_term = request.args.get('search_term')

    connection = sqlite3.connect('data.db')
    cursor = connection.cursor()

    query = f"SELECT * FROM professeur WHERE {critere} LIKE ?"
    cursor.execute(query, ('%' + search_term + '%',))
    professeurs = cursor.fetchall()

    connection.close()

    return render_template('professeur.html', professeurs=professeurs)


@app.route('/prof_login', methods=['GET', 'POST'])
def prof_login():
    professeur = None   

    if request.method == 'POST':
        prof_id = request.form.get('IDprof')
        prof_nom = request.form.get('Nom_Prof')

        connection = sqlite3.connect('data.db')
        cursor = connection.cursor()
        
        cursor.execute('''
            SELECT * FROM professeur
            WHERE IDprof = ? AND Nom_Prof = ?
        ''', (prof_id, prof_nom))

        professeur = cursor.fetchone()

        connection.close()

        if professeur:
            return render_template('profinfo.html', professeur=professeur)
        else:
            return render_template('prof.html', error_message='ID ou nom incorrect. Veuillez réessayer.', professeur=professeur)

    return render_template('prof.html', professeur=professeur)



    
@app.route('/ajouter_professeur', methods=['POST'])
def ajouter_professeur():
    if request.method == 'POST':
        nom = request.form['nom']
        prenom = request.form['prenom']
        telephone = request.form['telephone']
        email_prof = request.form['email_prof']
        type_prof = request.form['type_prof']

        connection = sqlite3.connect('data.db')
        cursor = connection.cursor()

        cursor.execute('''
            INSERT INTO professeur (Nom_prof, Prenom_prof, Telephone_prof, Email_prof,
                                    type_prof)
            VALUES (?, ?, ?, ?, ?)
        ''', (nom, prenom, telephone, email_prof,type_prof))

        connection.commit()
        connection.close()

    return redirect(url_for('afficher_professeurs'))


@app.route('/supprimer_professeur/<int:professeur_id>', methods=['POST'])
def supprimer_professeur(professeur_id):
    connection = sqlite3.connect('data.db')
    cursor = connection.cursor()

    cursor.execute('DELETE FROM professeur WHERE IDprof = ?', (professeur_id,))
    
    connection.commit()
    connection.close()

    return redirect(url_for('afficher_professeurs'))

def table_exists(cursor, table_name):
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    return cursor.fetchone() is not None



def init_db():
    print("Initializing the database...")
    try:
        connection = sqlite3.connect('data.db')
        cursor = connection.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT,
                prenom TEXT,
                email TEXT,
                choix TEXT,
                type TEXT,
                niveau TEXT,
                CNE TEXT,
                matiere TEXT,
                langue TEXT,
                formation TEXT,
                group_id INTEGER  -- Add the group_id column
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                niveau TEXT,
                id_prof INTEGER,
                heure_debut TEXT,
                heure_fin TEXT,
                jour TEXT,
                capacity INTEGER,
                FOREIGN KEY (id_prof) REFERENCES professeur (IDprof)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS paiement (
                id INTEGER PRIMARY KEY AUTOINCREMENT,      
                student_id INTEGER,
                montant INT,       
                date_paiement TEXT,
                sessions_payer INTEGER,
                type_de_seance TEXT,        
                FOREIGN KEY(student_id) REFERENCES registrations(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS absence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                group_id INTEGER,       
                date TEXT 
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS presence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                etudiant_id INTEGER,
                date_presence TEXT,
                FOREIGN KEY(etudiant_id) REFERENCES registrations(id)
            )
        ''')
        if not table_exists(cursor, 'salle'):
            cursor.execute('''
                CREATE TABLE salle (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    numsalle INTEGER,
                    idgroupe INTEGER,
                    heure_debut TEXT,
                    heure_fin TEXT,
                    jour TEXT,
                    FOREIGN KEY(idgroupe) REFERENCES groups(id)
                )
            ''')

            jours = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi']
            creneaux = ['17:00-19:00', '19:00-21:00']

            for numsalle in range(1, 7):  
                for jour in jours:
                    for creneau in creneaux:
                        horaires = creneau.split('-')
                        heure_debut = horaires[0]
                        heure_fin = horaires[1]
                        cursor.execute('''
                            INSERT INTO salle (numsalle, idgroupe, heure_debut, heure_fin, jour)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (numsalle, None, heure_debut, heure_fin, jour))

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS professeur (
             IDprof INTEGER PRIMARY KEY AUTOINCREMENT,
             Nom_Prof TEXT,
             Prenom_prof TEXT,
             Telephone_prof TEXT,
             Email_prof TEXT,
             type_prof TEXT
            )
        ''')

        cursor.execute('SELECT * FROM professeur')
        existing_professors = cursor.fetchall()

        if not existing_professors:
                mes_professeurs = [('AOUN', 'Fouzia', '0123456789', 'aoun1.Fz@gmail.com','anglais'),
               ('Razin', 'Hassan', '0234567891', 'Razin.hassan@gmail.com','francais'),
               ('SALEM', 'Salma', '0345678912', 'Salm.sm@gmail.com', 'espagnol'),
               ('AOUN', 'Fouzia', '0123456789', 'aoun1.Fz@gmail.com','italie'),
               ('Razin', 'Hassan', '0234567891', 'Razin.hassan@gmail.com','allmagne'),
               ('SALEM', 'Salma', '0345678912', 'Salm.sm@gmail.com','arabe'),
               ('EL ALAMI', 'Youssef', '0654789213', 'el.youssef@gmail.com','langage c'),
               ('BENJELLOUN', 'Fatima', '0778896321', 'benjelloun.fatima@gmail.com','langage python' ),
               ('ABOU', 'Ahmed', '0887654321', 'abou.ahmed@gmail.com','svt'),
               ('FAROUKI', 'Nadia', '0912345678', 'farouki.nadia@gmail.com','physique'),
               ('BERRADA', 'Karim', '0998765432', 'berrada.karim@gmail.com', 'math'),
               ('ZAHIR', 'Samira', '0567890123', 'zahir.samira@gmail.com','developpement web' ),
               ('ESSAIDI', 'Rachid', '0678901234', 'essaidi.rachid@gmail.com','geographie' ),
               ('EL KHALIL', 'Laila', '0556789012', 'elkhalil.laila@gmail.com','education_islamique' ),
               ('ZAROUAL', 'Omar', '0689012345', 'zaroual.omar@gmail.com','philosophie'),
               ('CHAMI', 'Nawal', '0765432109', 'chami.nawal@gmail.com', 'physique'),
               ('BENZAKOUR', 'Khalid', '0832109876', 'benzakour.khalid@gmail.com', 'developpement web'),
               ('LAAROUSSI', 'Amina', '0954321098', 'laaroussi.amina@gmail.com', 'espagnol'),
               ('ZEMMOURI', 'Yassir', '0976543210', 'zemouri.yassir@gmail.com','arabe'),
               ('CHAFAI', 'Hanane', '0732198765', 'chafai.hanane@gmail.com','math'),
               ('EL MOUSSAOUI', 'Abdel', '0823456789', 'elmoussaoui.abdel@gmail.com','langage python'),
               ('EL MAHDAOUI', 'Sara', '0998765432', 'elmahdaoui.sara@gmail.com', 'allmagne'),
               ('ZEROUALI', 'Mohamed', '0712345678', 'zerouali.mohamed@gmail.com','italie' ),
               ('EL KADIRI', 'Zahra', '0634567890', 'elkadiri.zahra@gmail.com', 'education_islamique'),
               ('EL OUAZZANI', 'Sofia', '0987654321', 'elouazzani.sofia@gmail.com','langage c' )]
                cursor.executemany('''
                INSERT INTO professeur (Nom_Prof, Prenom_prof, Telephone_prof, Email_prof,type_prof)VALUES (?, ?, ?, ?, ?)''', mes_professeurs)
        
        connection.commit()
        connection.close()
        print("Database initialization complete.")
    except Exception as e:
        print(f"Error during database initialization: {e}")

init_db()

@app.route('/registrations')
def registrations():
    connection = sqlite3.connect('data.db')
    cursor = connection.cursor()
    cursor.execute('SELECT * FROM registrations')
    registrations_data = cursor.fetchall()
    connection.close()
    return render_template('registrations.html', registrations=registrations_data)

if __name__ == '__main__':
    app.run(debug=True)