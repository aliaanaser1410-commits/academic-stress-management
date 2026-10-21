import os
os.environ["KERAS_BACKEND"] = "torch"
import cv2
import numpy as np
import streamlit as st
from sklearn import preprocessing
from sklearn.model_selection import train_test_split
from keras.models import Sequential
from keras.layers import Dense, Flatten, Input, Conv2D, MaxPool2D
from keras import optimizers
from sklearn.utils import shuffle

st.set_page_config(page_title="Fruit Classification Dashboard", page_icon="🍎", layout="centered")

st.title("🍎 Fruit & Plant Classification System")
st.write("ارفع صورة أي فاكهة أو خضار والتطبيق هيتوقع نوعها!")

path = 'ColorfulOriginal'
Foldernames = ['Banana', 'Carrot', 'Corn', 'Apple', 'Tomato', 'Strawberry', 'Potato', 'Plum', 'Pear', 'Orange', 'Lemon', 'LadyFinger']
im_size = 50

@st.cache_resource
def load_and_train_model():
    Plant_images = []
    Plant_types = []

    for m in Foldernames:
        folder_path = os.path.join(path, m)
        if os.path.exists(folder_path):
            files_names = os.listdir(folder_path)
            for n in files_names:
                im = cv2.imread(os.path.join(folder_path, n))
                if im is not None:
                    image = cv2.resize(im, (im_size, im_size), interpolation=cv2.INTER_AREA)
                    Plant_images.append(image / 255.0)
                    Plant_types.append(m)

    Plant_images = np.array(Plant_images)
    Plant_types = np.array(Plant_types)

    X, Y = shuffle(Plant_images, Plant_types, random_state=42)

    Pr = preprocessing.LabelEncoder()
    Yencoded = Pr.fit_transform(Y)
    encoded_classes = Pr.classes_

    X_train, X_test, Y_train, Y_test = train_test_split(X, Yencoded, test_size=0.2)

    model = Sequential([
        Input(shape=(im_size, im_size, 3)),
        Conv2D(filters=32, kernel_size=(3, 3), strides=1, padding='same', activation='relu'),
        MaxPool2D(pool_size=(2, 2), strides=2, padding='valid'),
        Flatten(),
        Dense(128, activation='relu'),
        Dense(len(Foldernames), activation='softmax')
    ])

    opt = optimizers.Adam(learning_rate=0.001)
    model.compile(optimizer=opt, loss='sparse_categorical_crossentropy', metrics=['accuracy'])
    model.fit(X_train, Y_train, validation_data=(X_test, Y_test), epochs=5, batch_size=32, verbose=0)
    
    loss, acc = model.evaluate(X_test, Y_test, verbose=0)
    return model, encoded_classes, acc

with st.spinner("جاري تحميل النموذج والبيانات..."):
    model, encoded_classes, acc = load_and_train_model()

st.success(f"Model Accuracy: {acc * 100:.2f}%")
st.markdown("---")

uploaded_file = st.file_uploader("اختر صورة فاكهة للتنبؤ بها", type=["jpg", "png", "jpeg"])

if uploaded_file is not None:
    file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
    image = cv2.imdecode(file_bytes, 1)
    
    col1, col2 = st.columns(2)
    with col1:
        st.image(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), caption="الصورة المرفوعة", use_column_width=True)
    
    with col2:
        if image is not None:
            Xn = cv2.resize(image, (im_size, im_size))
            Xnew = np.reshape(Xn, (1, im_size, im_size, 3)) / 255.0
            
            Ypred = model.predict(Xnew)
            predicted_name = encoded_classes[np.argmax(Ypred)]
            confidence = np.max(Ypred) * 100
            
            st.markdown("### النتيجة:")
            st.success(f"النوع المتوقع: **{predicted_name}**")
            st.info(f"نسبة الثقة: **{confidence:.2f}%**")
