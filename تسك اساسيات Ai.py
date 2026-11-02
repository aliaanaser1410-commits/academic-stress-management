# استيراد المكتبات
import numpy as np
from sklearn import datasets
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score

# تحميل بيانات بسيطة (مثال: بيانات الأزهار Iris)
iris = datasets.load_iris()
X = iris.data
y = iris.target

# تقسيم البيانات إلى تدريب واختبار
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

# إنشاء نموذج SVM
model = SVC(kernel='linear')  # ممكن تغير kernel إلى 'rbf' أو 'poly'

# تدريب النموذج
model.fit(X_train, y_train)

# التنبؤ على بيانات الاختبار
y_pred = model.predict(X_test)

# حساب الدقة
print("Accuracy:", accuracy_score(y_test, y_pred))