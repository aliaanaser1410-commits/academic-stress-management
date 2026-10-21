##    الكود بعد اضافه الداش بورد

import os
os.environ["KERAS_BACKEND"] = "torch"
import cv2
import numpy as np
from sklearn import preprocessing
from sklearn.model_selection import train_test_split
from keras.models import Sequential
from keras.layers import Dense, Flatten, Input, Conv2D, MaxPool2D
from keras import optimizers
from sklearn.utils import shuffle
import tkinter as tk
from tkinter import filedialog

path = r'C:\Users\ALfajr\Documents\ColorfulOriginal'
Foldernames = ['Banana', 'Carrot', 'Corn', 'Apple', 'Tomato', 'Strawberry', 'Potato', 'Plum', 'Pear', 'Orange', 'Lemon', 'LadyFinger']

im_size = 50
Plant_images = []
Plant_types = []

for m in Foldernames:
    files_names = os.listdir(path + '\\' + m)
    for n in files_names:
        im = cv2.imread(path + '\\' + m + '\\' + n)
        if im is not None:
            image = cv2.resize(im, (im_size, im_size), interpolation=cv2.INTER_AREA)
            Plant_images.append(image / 255)
            Plant_types.append(m)

Plant_images = np.array(Plant_images)
Plant_types = np.array(Plant_types)

X, Y = shuffle(Plant_images, Plant_types, random_state=42)

#  تقسيم البيانات
Pr = preprocessing.LabelEncoder()
Yencoded = Pr.fit_transform(Y)
encoded_classes = Pr.classes_

X_train, X_test, Y_train, Y_test = train_test_split(X, Yencoded, test_size=0.2)

#  CNN
model = Sequential()
model.add(Input(shape=(im_size, im_size, 3)))
model.add(Conv2D(filters=32, kernel_size=(3, 3), strides=1, padding='same'))
model.add(MaxPool2D(pool_size=(2 ,2), strides=2, padding='valid'))
model.add(Flatten())
model.add(Dense(128, activation='relu'))
model.add(Dense(len(Foldernames), activation='softmax'))

opt = optimizers.Adam(learning_rate=0.001)
model.compile(
    optimizer=opt,
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)

print("Training model, please wait...")
model.fit(X_train, Y_train, validation_data=(X_test, Y_test), epochs=15, batch_size=32)

loss, acc = model.evaluate(X_test, Y_test)
accuracy_text = f"Model Accuracy: {acc * 100:.2f}%"
print(accuracy_text)

#  تصميم الداشبورد 
root = tk.Tk()
root.title("Fruit Classification Dashboard")
root.geometry("480x380")
root.config(bg="#2c3e50")  

# عنوان الداشبورد
title_label = tk.Label(root, text="Fruit Classification System", font=("Helvetica", 16, "bold"), bg="#2c3e50", fg="#ecf0f1")
title_label.pack(pady=20)

# عرض نسبة الدقة على الداشبورد
acc_label = tk.Label(root, text=accuracy_text, font=("Helvetica", 13, "bold"), bg="#34495e", fg="#1abc9c", padx=15, pady=8)
acc_label.pack(pady=10)

# دالة لاختيار الصورة والتنبؤ بها
def predict_new_image():
    file_path = filedialog.askopenfilename()
    if file_path:
        X_new = cv2.imread(file_path)
        if X_new is not None:
            Xn = cv2.resize(X_new, (im_size, im_size))
            Xnew = np.reshape(Xn, (1, im_size, im_size, 3)) / 255.0
            
            Ypred = model.predict(Xnew)
            predicted_name = encoded_classes[np.argmax(Ypred)]
            
            # عرض النتيجة على الشاشة بلون واضح
            result_label.config(text=f"Prediction: {predicted_name}", fg="#2ecc71")
        else:
            result_label.config(text="Error: Could not read image!", fg="#e74c3c")

# زر اختيار الصورة
btn_browse = tk.Button(root, text="Select Image to Predict", command=predict_new_image, font=("Helvetica", 12, "bold"), bg="#2980b9", fg="white", activebackground="#3498db", activeforeground="white", padx=15, relief="flat", cursor="hand2")
btn_browse.pack(pady=20)

# مكان ظهور النتيجة
result_label = tk.Label(root, text="Prediction will appear here...", font=("Helvetica", 14), bg="#2c3e50", fg="#bdc3c7")
result_label.pack(pady=10)

root.mainloop()